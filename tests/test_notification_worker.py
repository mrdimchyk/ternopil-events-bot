from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event
from app.db.user_models import FavoriteNotification
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
async def test_worker_deduplicates_multi_source_event_for_one_subscription():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add_all([
        Event(external_id="karabas-1", group_key="g1", title="Event from KARABAS", start_at=now + timedelta(hours=23), source_id=1, source_url="https://karabas.com/event/1", status="active"),
        Event(external_id="teatr-1", group_key="g1", title="Event from Teatr", start_at=now + timedelta(hours=24), source_id=2, source_url="https://teatr.org.ua/event/1", status="active"),
    ])
    db.flush()
    subscribe_favorite(db, 10000000003, "g1")

    sender = FakeSender()
    assert await deliver_due_notifications(db, sender, now) == 1
    assert len(sender.messages) == 1
    assert "Event from KARABAS" in sender.messages[0][1]


@pytest.mark.asyncio
async def test_worker_does_not_mark_notification_when_delivery_fails():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(Event(external_id="e2", group_key="g2", title="Failed delivery", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/e2", status="active"))
    db.flush()
    subscribe_favorite(db, 10000000002, "g2")

    with pytest.raises(RuntimeError):
        await deliver_due_notifications(db, FailingSender(), now)

    subscription = db.query(FavoriteNotification).one()
    assert subscription.last_notified_at is None


class FailSecondSender:
    def __init__(self):
        self.calls = []

    async def send_message(self, chat_id: int, text: str):
        self.calls.append(chat_id)
        if len(self.calls) == 2:
            raise RuntimeError("second delivery failed")
        return object()


@pytest.mark.asyncio
async def test_worker_persists_successful_delivery_before_later_failure():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add_all([
        Event(external_id="e3", group_key="g3", title="First event", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/e3", status="active"),
        Event(external_id="e4", group_key="g4", title="Second event", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/e4", status="active"),
    ])
    db.flush()
    subscribe_favorite(db, 10000000003, "g3")
    subscribe_favorite(db, 10000000004, "g4")
    subscriptions = {row.group_key: row for row in db.query(FavoriteNotification).all()}

    with pytest.raises(RuntimeError, match="second delivery failed"):
        await deliver_due_notifications(db, FailSecondSender(), now)

    db.refresh(subscriptions["g3"])
    db.refresh(subscriptions["g4"])
    assert subscriptions["g3"].last_notified_at == now
    assert subscriptions["g4"].last_notified_at is None
