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
        Event(external_id="t1", group_key="g1", title="KARABAS event", start_at=tomorrow_local + timedelta(minutes=10), source_id=2, source_url="https://teatr.example/1", status="active"),
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
    assert "🎟️ <b>Event 0</b> — 22:30 · 250 грн" in digest
    assert "🎫 https://example.com/tickets" in digest
    assert "Event 14" in digest
    assert "Event 15" not in digest


def test_screenshot_variants_use_shared_canonicalization_and_hide_catalog():
    db = make_session()
    start = datetime(2026, 10, 4, 10, tzinfo=timezone.utc)
    titles = ['«Аладдін» (Тернопільський театр ім. Т. Г. Шевченка)',
              'Дитяча вистава «Аладдін» (Тернопільський театр ім. Т. Г. Шевченка)',
              '«Аладдін»',
              '«Аладдін» 4 жовтня 2026 13:00 Тернопіль Тернопільський театр від 150₴ Квитки']
    for index, title in enumerate(titles):
        db.add(Event(external_id=str(index), group_key=f'key{index}', title=title,
                     start_at=start, source_id=index + 1, source_url=f'https://example.com/{index}'))
    db.add(Event(external_id='catalog', group_key='catalog',
                 title='Concerts and events in Ternopil, Ukraine', start_at=start,
                 source_id=10, source_url='https://ticketsfest.com.ua/en/events/ternopil/'))
    db.commit()
    now = datetime(2026, 10, 3, 20, 43, tzinfo=timezone.utc)
    assert len(tomorrow_events(db, now)) == 1
    with patch('app.jobs.daily_digest.SessionLocal', return_value=db):
        digest = build_tomorrow_digest(now)
    assert digest.count('🎟️') == 1
    assert '13:00' in digest
    assert '04.10.2026' in digest
    assert 'TicketsFest' not in digest
    assert 'Concerts and events' not in digest


def test_tomorrow_keeps_distinct_showtimes_even_with_same_group_key():
    db = make_session()
    for index, hour in enumerate([10, 15]):
        db.add(Event(external_id=str(index), group_key='legacy-same', title='Аладдін',
                     start_at=datetime(2026, 10, 4, hour, tzinfo=timezone.utc),
                     source_id=index + 1, source_url=f'https://example.com/{index}'))
    db.commit()
    assert len(tomorrow_events(db, datetime(2026, 10, 3, 12, tzinfo=timezone.utc))) == 2


def test_tomorrow_uses_utc_bounds_at_local_midnight():
    db = make_session()
    for index, start in enumerate([
        datetime(2026, 10, 3, 20, 59, tzinfo=timezone.utc),
        datetime(2026, 10, 3, 21, 0, tzinfo=timezone.utc),
        datetime(2026, 10, 4, 20, 59, tzinfo=timezone.utc),
        datetime(2026, 10, 4, 21, 0, tzinfo=timezone.utc),
    ]):
        db.add(Event(external_id=str(index), group_key=str(index), title=f'Подія {index}',
                     start_at=start, source_id=1, source_url=f'https://example.com/{index}'))
    db.commit()
    assert [e.external_id for e in tomorrow_events(
        db, datetime(2026, 10, 3, 20, 43, tzinfo=timezone.utc))] == ['1', '2']


def test_digest_escapes_source_text_and_formats_naive_db_time():
    events = [SimpleNamespace(title='Rock & <Roll>', start_at=datetime(2026, 10, 4, 16),
                              price_text='<450>', ticket_url='https://example.com/?a=1&b=2')]
    with patch('app.jobs.daily_digest.tomorrow_events', return_value=events):
        digest = build_tomorrow_digest(datetime(2026, 10, 3, 12, tzinfo=timezone.utc))
    assert 'Rock &amp; &lt;Roll&gt;' in digest
    assert '19:00' in digest
    assert '&lt;450&gt;' in digest


def test_empty_digest_includes_target_date_in_winter():
    with patch('app.jobs.daily_digest.tomorrow_events', return_value=[]):
        digest = build_tomorrow_digest(datetime(2026, 12, 1, 22, 10, tzinfo=timezone.utc))
    assert '03.12.2026' in digest
