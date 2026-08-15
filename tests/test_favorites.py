from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Event, Favorite, Source
from app.services.favorites import add_favorite, favorite_events, favorite_group_keys, remove_favorite


def make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def make_event(source_id: int, external_id: str, group_key: str, start_at: datetime) -> Event:
    return Event(
        external_id=external_id,
        group_key=group_key,
        title="Test event",
        start_at=start_at,
        source_id=source_id,
        source_url=f"https://example.com/{external_id}",
        status="active",
    )


def test_favorite_is_idempotent_and_user_scoped():
    session = make_session()
    session.add(Source(id=1, name="Test", base_url="https://example.com"))
    session.commit()
    assert add_favorite(session, 9_000_000_001, "group-a") is True
    assert add_favorite(session, 9_000_000_001, "group-a") is False
    assert favorite_group_keys(session, 9_000_000_001) == {"group-a"}
    assert favorite_group_keys(session, 9_000_000_002) == set()


def test_favorite_events_keep_canonical_sources_together():
    session = make_session()
    session.add(Source(id=1, name="A", base_url="https://a.example"))
    session.add(Source(id=2, name="B", base_url="https://b.example"))
    now = datetime.now()
    session.add_all([
        make_event(1, "a1", "group-a", now + timedelta(days=1)),
        make_event(2, "b1", "group-a", now + timedelta(days=1)),
        make_event(1, "a2", "group-b", now + timedelta(days=1)),
    ])
    session.commit()
    add_favorite(session, 42, "group-a")

    result = favorite_events(session, 42, now)

    assert len(result) == 1
    assert len(result[0].sources) == 2


def test_remove_favorite():
    session = make_session()
    add_favorite(session, 42, "group-a")
    assert remove_favorite(session, 42, "group-a") is True
    assert remove_favorite(session, 42, "group-a") is False
    assert session.query(Favorite).count() == 0
