from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models import Base, Source, SourceRun
from app.services.source_health import source_health_report


def session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, expire_on_commit=False)()


def add_runs(db, source, counts, statuses=None):
    statuses = statuses or ["success"] * len(counts)
    db.add(source)
    db.flush()
    now = datetime(2026, 8, 16, 12, 0)
    for index, (count, status) in enumerate(zip(counts, statuses, strict=True)):
        db.add(
            SourceRun(
                source_id=source.id,
                started_at=now - timedelta(hours=index),
                finished_at=now - timedelta(hours=index),
                status=status,
                collected_count=count,
                error_text="collector failed" if status == "error" else None,
            )
        )
    db.commit()


def test_healthy_source_uses_recent_baseline():
    db = session()
    add_runs(db, Source(name="KARABAS", base_url="https://example.com"), [47, 46, 49, 45])
    report = source_health_report(db, ["KARABAS"])
    assert report["overall"] == "healthy"
    assert report["sources"]["KARABAS"]["status"] == "healthy"


def test_zero_result_is_degraded_unless_explicitly_allowed():
    db = session()
    add_runs(db, Source(name="Broken", base_url="https://example.com"), [0, 12, 11])
    report = source_health_report(db, ["Broken"])
    assert report["overall"] == "degraded"
    assert report["sources"]["Broken"]["zero_result"] is True


def test_allowed_empty_source_is_not_marked_zero_result():
    db = session()
    add_runs(db, Source(name="TicketsBox", base_url="https://example.com"), [0, 0, 0])
    report = source_health_report(db, ["TicketsBox"], allow_empty_sources={"TicketsBox"})
    assert report["sources"]["TicketsBox"]["zero_result"] is False
    assert report["sources"]["TicketsBox"]["status"] == "healthy"


def test_large_drop_is_degraded():
    db = session()
    add_runs(db, Source(name="SourceA", base_url="https://example.com"), [8, 20, 22, 21])
    report = source_health_report(db, ["SourceA"])
    assert report["sources"]["SourceA"]["anomaly"] is True
    assert report["sources"]["SourceA"]["status"] == "degraded"


def test_latest_error_is_down_and_included_in_overall_status():
    db = session()
    add_runs(db, Source(name="SourceA", base_url="https://example.com"), [0, 20, 21], ["error", "success", "success"])
    report = source_health_report(db, ["SourceA"])
    assert report["overall"] == "degraded"
    assert report["sources"]["SourceA"]["status"] == "down"
    assert report["sources"]["SourceA"]["latest_status"] == "error"
