from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event, Source
from app.db.user_models import FavoriteNotification, TelegramUser
from app.services.notification_worker import deliver_due_notifications
from app.services.notifications import subscribe_favorite


class FakeSender:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id: int, text: str):
        self.messages.append((chat_id, text))
        return object()


@pytest.mark.asyncio
async def test_postgres_notification_delivery_is_idempotent():
    engine = create_engine("postgresql+psycopg://events:events@localhost:5432/events")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    db = Session()
    now = datetime(2026, 8, 16, 12, 0)
    telegram_id = 900000001
    group_key = "pg-integration-test"
    source_name = "Postgres integration test"

    try:
        source = Source(name=source_name, base_url="https://example.com")
        db.add(source)
        db.flush()
        db.add(
            Event(
                external_id="pg-e1",
                group_key=group_key,
                title="Postgres integration event",
                start_at=now + timedelta(hours=23),
                source_id=source.id,
                source_url="https://example.com/pg-e1",
                status="active",
            )
        )
        db.flush()
        subscribe_favorite(db, telegram_id, group_key)

        sender = FakeSender()
        assert await deliver_due_notifications(db, sender, now) == 1
        assert len(sender.messages) == 1
        assert sender.messages[0][0] == telegram_id

        assert await deliver_due_notifications(db, sender, now) == 0
        assert len(sender.messages) == 1
    finally:
        db.rollback()
        db.execute(delete(FavoriteNotification).where(FavoriteNotification.group_key == group_key))
        user = db.query(TelegramUser).filter(TelegramUser.telegram_id == telegram_id).one_or_none()
        if user is not None:
            db.delete(user)
        db.execute(delete(Event).where(Event.group_key == group_key))
        db.execute(delete(Source).where(Source.name == source_name))
        db.commit()
        db.close()
        engine.dispose()
