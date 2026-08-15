from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event
from app.db.user_models import FavoriteNotification, TelegramUser
from app.services.notifications import due_notifications, subscribe_favorite, unsubscribe_favorite


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_subscription_is_idempotent_and_user_scoped():
    db = session()
    assert subscribe_favorite(db, 10000000001, "g1") is True
    assert subscribe_favorite(db, 10000000001, "g1") is False
    assert subscribe_favorite(db, 10000000002, "g1") is True
    assert db.query(FavoriteNotification).count() == 2


def test_due_notification_is_emitted_once():
    db = session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(Event(external_id="e1", group_key="g1", title="Test", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com", status="active"))
    db.flush()
    subscribe_favorite(db, 10000000001, "g1")
    due = due_notifications(db, now)
    assert len(due) == 1
    subscription, item = due[0]
    assert item.group_key == "g1"
    subscription.last_notified_at = now
    db.commit()
    assert due_notifications(db, now) == []


def test_unsubscribe_removes_subscription():
    db = session()
    subscribe_favorite(db, 10000000001, "g1")
    assert unsubscribe_favorite(db, 10000000001, "g1") is True
    assert unsubscribe_favorite(db, 10000000001, "g1") is False
