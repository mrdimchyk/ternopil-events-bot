from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event
from app.services.notification_worker import deliver_due_notifications
from app.services.notifications import subscribe_favorite


class FakeSender:
    def __init__(self):
        self.messages = []

    async def send_message(self, chat_id: int, text: str):
        self.messages.append((chat_id, text))
        return object()


class FailingSender:
    async def send_message(self, chat_id: int, text: str):
        raise RuntimeError("delivery failed")


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


@pytest.mark.asyncio
async def test_worker_delivers_once_and_second_run_is_idempotent():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(Event(external_id="e1", group_key="g1", title="Test event", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/e1", status="active"))
    db.flush()
    subscribe_favorite(db, 10000000001, "g1")

    sender = FakeSender()
    assert await deliver_due_notifications(db, sender, now) == 1
    assert len(sender.messages) == 1
    assert sender.messages[0][0] == 10000000001
    assert "Test event" in sender.messages[0][1]

    assert await deliver_due_notifications(db, sender, now) == 0
    assert len(sender.messages) == 1


@pytest.mark.asyncio
async def test_worker_does_not_mark_notification_when_delivery_fails():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(Event(external_id="e2", group_key="g2", title="Failed delivery", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/e2", status="active"))
    db.flush()
    subscribe_favorite(db, 10000000002, "g2")

    with pytest.raises(RuntimeError):
        await deliver_due_notifications(db, FailingSender(), now)

    subscription = db.query(__import__("app.db.user_models", fromlist=["FavoriteNotification"]).FavoriteNotification).one()
    assert subscription.last_notified_at is None
