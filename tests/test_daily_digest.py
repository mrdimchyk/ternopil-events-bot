from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

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
    tomorrow_local = datetime(2026, 8, 18, 18, 0, tzinfo=timezone.utc)
    db.add_all([
        Event(external_id="k1", group_key="g1", title="KARABAS event", start_at=tomorrow_local, source_id=1, source_url="https://karabas.example/1", status="active"),
        Event(external_id="t1", group_key="g1", title="Teatr duplicate", start_at=tomorrow_local + timedelta(hours=1), source_id=2, source_url="https://teatr.example/1", status="active"),
        Event(external_id="next", group_key="g2", title="Next day", start_at=tomorrow_local + timedelta(days=1), source_id=1, source_url="https://example.com/next", status="active"),
    ])
    db.commit()

    events = tomorrow_events(db, now)

    assert [event.group_key for event in events] == ["g1"]
    assert events[0].title == "KARABAS event"


def test_tomorrow_events_ignore_inactive_events():
    db = make_session()
    now = datetime(2026, 8, 16, 12, 0, tzinfo=timezone.utc)
    db.add(Event(
        external_id="inactive",
        group_key="g1",
        title="Inactive event",
        start_at=now + timedelta(days=1, hours=6),
        source_id=1,
        source_url="https://example.com/inactive",
        status="cancelled",
    ))
    db.commit()

    assert tomorrow_events(db, now) == []


def test_tomorrow_digest_formats_events_and_caps_output():
    events = [
        SimpleNamespace(
            title=f"Event {index}",
            start_at=datetime(2026, 8, 18, 19, 30, tzinfo=timezone.utc),
            price_text="250 грн" if index == 0 else None,
            ticket_url="https://example.com/tickets" if index == 0 else None,
        )
        for index in range(16)
    ]

    with patch("app.jobs.daily_digest.tomorrow_events", return_value=events):
        digest = build_tomorrow_digest(datetime(2026, 8, 17, 8, 0, tzinfo=timezone.utc))

    assert "🌙 <b>Що цікавого завтра в Тернополі</b>" in digest
    assert "🎟️ <b>Event 0</b> — 19:30 · 250 грн" in digest
    assert "🎫 https://example.com/tickets" in digest
    assert "Event 14" in digest
    assert "Event 15" not in digest
