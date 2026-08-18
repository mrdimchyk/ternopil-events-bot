from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event
from app.db.user_models import FavoriteNotification
from app.services.notifications import (
    due_notifications,
    notification_group_keys,
    subscribe_favorite,
    unsubscribe_favorite,
)


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


def test_notification_state_expands_across_canonical_source_variants():
    db = session()
    start = datetime(2026, 8, 23, 19, 0)
    db.add_all(
        [
            Event(external_id="source-a", group_key="g1", title="Jamala", start_at=start, source_id=1, source_url="https://example.com/a", status="active"),
            Event(external_id="source-b", group_key="g2", title="Jamala", start_at=start, source_id=2, source_url="https://example.com/b", status="active"),
        ]
    )
    db.flush()

    subscribe_favorite(db, 10000000001, "g2")

    assert notification_group_keys(db, 10000000001) == {"g1", "g2"}
    assert unsubscribe_favorite(db, 10000000001, "g1") is True
    assert notification_group_keys(db, 10000000001) == set()


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


def test_due_notification_handles_multiple_source_events_in_same_group():
    db = session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add_all(
        [
            Event(external_id="karabas-1", group_key="g1", title="Test from KARABAS", start_at=now + timedelta(hours=23), source_id=1, source_url="https://karabas.com/event/1", status="active"),
            Event(external_id="teatr-1", group_key="g1", title="Test from Teatr", start_at=now + timedelta(hours=24), source_id=2, source_url="https://teatr.org.ua/event/1", status="active"),
        ]
    )
    db.flush()
    subscribe_favorite(db, 10000000001, "g1")
    due = due_notifications(db, now)
    assert len(due) == 1
    assert due[0][1].event_id == 1
    assert due[0][1].title == "Test from KARABAS"


def test_due_notification_uses_event_id_as_deterministic_tiebreaker():
    db = session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add_all(
        [
            Event(external_id="source-a", group_key="g1", title="First inserted", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/a", status="active"),
            Event(external_id="source-b", group_key="g1", title="Second inserted", start_at=now + timedelta(hours=23), source_id=2, source_url="https://example.com/b", status="active"),
        ]
    )
    db.flush()
    subscribe_favorite(db, 10000000001, "g1")
    due = due_notifications(db, now)
    assert len(due) == 1
    assert due[0][1].event_id == 1


def test_notification_state_survives_session_restart(tmp_path):
    db_path = tmp_path / "notification-persistence.sqlite"
    url = f"sqlite:///{db_path}"
    now = datetime(2026, 8, 16, 12, 0)

    engine1 = create_engine(url)
    Base.metadata.create_all(engine1)
    Session1 = sessionmaker(bind=engine1, expire_on_commit=False)
    db1 = Session1()
    db1.add(Event(external_id="persistent-1", group_key="persistent-group", title="Persistent event", start_at=now + timedelta(hours=23), source_id=1, source_url="https://example.com/persistent", status="active"))
    db1.flush()
    assert subscribe_favorite(db1, 10000000001, "persistent-group") is True
    due = due_notifications(db1, now)
    assert len(due) == 1
    due[0][0].last_notified_at = now
    db1.commit()
    db1.close()
    engine1.dispose()

    engine2 = create_engine(url)
    Session2 = sessionmaker(bind=engine2, expire_on_commit=False)
    db2 = Session2()
    subscription = db2.query(FavoriteNotification).one()
    event = db2.query(Event).one()
    assert subscription.group_key == "persistent-group"
    assert subscription.last_notified_at == now
    assert event.external_id == "persistent-1"
    assert due_notifications(db2, now) == []
    db2.close()
    engine2.dispose()


def test_unsubscribe_removes_subscription():
    db = session()
    subscribe_favorite(db, 10000000001, "g1")
    assert unsubscribe_favorite(db, 10000000001, "g1") is True
    assert unsubscribe_favorite(db, 10000000001, "g1") is False
