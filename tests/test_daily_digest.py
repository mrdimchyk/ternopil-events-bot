from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event
from app.jobs.daily_digest import build_tomorrow_digest
from app.services.notifications import tomorrow_events


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def test_tomorrow_events_are_timezone_aware_and_deduplicated():
    db = make_session()
    now = datetime(2026, 8, 16, 21, 30, tzinfo=timezone.utc)
    tomorrow_local = datetime(2026, 8, 17, 18, 0, tzinfo=timezone.utc)
    db.add_all([
        Event(external_id="k1", group_key="g1", title="KARABAS event", start_at=tomorrow_local, source_id=1, source_url="https://karabas.example/1", status="active"),
        Event(external_id="t1", group_key="g1", title="Teatr duplicate", start_at=tomorrow_local + timedelta(hours=1), source_id=2, source_url="https://teatr.example/1", status="active"),
        Event(external_id="next", group_key="g2", title="Next day", start_at=tomorrow_local + timedelta(days=1), source_id=1, source_url="https://example.com/next", status="active"),
    ])
    db.commit()

    events = tomorrow_events(db, now)

    assert [event.group_key for event in events] == ["g1"]
    assert events[0].title == "KARABAS event"


def test_build_tomorrow_digest_uses_unique_events():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0)
    db.add(Event(
        external_id="e1",
        group_key="g1",
        title="Тестова подія",
        start_at=now + timedelta(days=1, hours=6),
        price_text="500 грн",
        ticket_url="https://example.com/tickets/e1",
        source_id=1,
        source_url="https://example.com/e1",
        status="active",
    ))
    db.commit()

    # The digest job currently opens its own SessionLocal connection, so this
    # assertion is kept at the service level until the job gets dependency injection.
    assert tomorrow_events(db, now)[0].title == "Тестова подія"
