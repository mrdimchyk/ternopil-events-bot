from datetime import datetime, timedelta

import pytest

from app.db.models import Base, Event
from app.db.user_models import FavoriteNotification
from app.services.notifications import subscribe_favorite
from app.services.notification_worker import deliver_due_notifications


class FailingSender:
    async def send_message(self, chat_id: int, text: str) -> object:
        raise RuntimeError("telegram unavailable")


class RecordingSender:
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str) -> object:
        self.messages.append((chat_id, text))
        return object()


def session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


@pytest.mark.asyncio
async def test_delivery_failure_does_not_mark_notification_as_sent():
    db = session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(
        Event(
            external_id="worker-1",
            group_key="g1",
            title="Worker test",
            start_at=now + timedelta(hours=23),
            source_id=1,
            source_url="https://example.com/worker-1",
            status="active",
        )
    )
    db.flush()
    subscribe_favorite(db, 10000000001, "g1")
    subscription = db.query(FavoriteNotification).one()

    with pytest.raises(RuntimeError, match="telegram unavailable"):
        await deliver_due_notifications(db, FailingSender(), now)

    db.refresh(subscription)
    assert subscription.last_notified_at is None


@pytest.mark.asyncio
async def test_successful_delivery_marks_notification_after_send():
    db = session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(
        Event(
            external_id="worker-2",
            group_key="g2",
            title="Successful worker test",
            start_at=now + timedelta(hours=23),
            source_id=1,
            source_url="https://example.com/worker-2",
            status="active",
        )
    )
    db.flush()
    subscribe_favorite(db, 10000000001, "g2")
    subscription = db.query(FavoriteNotification).one()
    sender = RecordingSender()

    delivered = await deliver_due_notifications(db, sender, now)

    assert delivered == 1
    assert len(sender.messages) == 1
    db.refresh(subscription)
    assert subscription.last_notified_at == now
