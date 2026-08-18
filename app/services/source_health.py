from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from statistics import median

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Event, Source, SourceRun


FRESHNESS_WINDOW_DAYS = 7


@dataclass(slots=True)
class SourceHealth:
    source: str
    status: str
    runs_checked: int
    latest_status: str | None
    latest_collected: int | None
    median_collected: float | None
    zero_result: bool
    anomaly: bool
    events_next_7d: int
    next_event_at: datetime | None
    freshness_stale: bool
    message: str


def _status_for_runs(
    source_name: str,
    runs: list[SourceRun],
    *,
    allow_empty: bool,
    events_next_7d: int = 0,
    next_event_at: datetime | None = None,
    minimum_runs: int = 3,
) -> SourceHealth:
    latest = runs[0] if runs else None
    counts = [run.collected_count for run in runs if run.status == "success"]
    latest_count = latest.collected_count if latest else None
    zero_result = bool(latest and latest.status == "success" and latest_count == 0 and not allow_empty)

    # Freshness is deliberately derived from the two query results rather than
    # comparing datetime objects. Event.start_at can be naive after SQLite
    # round-trips while `now` may be timezone-aware; the business rule does not
    # need that representation detail:
    #   - events in the next window => healthy
    #   - no near-term events but a later event exists => quiet
    #   - no future events at all => healthy
    freshness_stale = bool(
        latest
        and latest.status == "success"
        and latest_count
        and events_next_7d == 0
        and next_event_at is not None
        and not allow_empty
    )

    baseline = median(counts[1:]) if len(counts) > 1 else None
    anomaly = False
    if latest and latest.status == "error":
        anomaly = True
    elif latest_count is not None and latest.status == "success" and latest_count > 0 and baseline and baseline >= 5:
        anomaly = latest_count < baseline * 0.5

    if not runs:
        status = "unknown"
        message = "No collection history yet."
    elif latest.status == "error":
        status = "down"
        message = latest.error_text or "Latest collector run failed."
    elif zero_result:
        status = "degraded"
        message = "Latest run returned zero events; inspect the collector/parser."
    elif anomaly:
        status = "degraded"
        message = f"Latest count {latest_count} is below 50% of the historical median {baseline:.1f}."
    elif freshness_stale:
        status = "quiet"
        if next_event_at is not None:
            message = (
                f"No active events in the next {FRESHNESS_WINDOW_DAYS} days; "
                f"next event is {next_event_at.isoformat()}."
            )
        else:
            message = f"No active events in the next {FRESHNESS_WINDOW_DAYS} days."
    elif len(runs) < minimum_runs:
        status = "warming"
        message = f"Only {len(runs)} run(s) available; anomaly baseline is still warming up."
    else:
        status = "healthy"
        message = "Recent collection results and near-term event coverage are healthy."

    return SourceHealth(
        source=source_name,
        status=status,
        runs_checked=len(runs),
        latest_status=latest.status if latest else None,
        latest_collected=latest_count,
        median_collected=float(baseline) if baseline is not None else None,
        zero_result=zero_result,
        anomaly=anomaly,
        events_next_7d=events_next_7d,
        next_event_at=next_event_at,
        freshness_stale=freshness_stale,
        message=message,
    )


def source_health_report(
    session: Session,
    source_names: list[str],
    *,
    allow_empty_sources: set[str] | None = None,
    history_limit: int = 7,
    now: datetime | None = None,
    freshness_window_days: int = FRESHNESS_WINDOW_DAYS,
) -> dict[str, object]:
    allow_empty_sources = allow_empty_sources or set()
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    freshness_end = current + timedelta(days=freshness_window_days)
    results: dict[str, dict[str, object]] = {}

    for source_name in source_names:
        source = session.scalar(select(Source).where(Source.name == source_name))
        runs = []
        events_next_7d = 0
        next_event_at = None
        if source is not None:
            runs = list(
                session.scalars(
                    select(SourceRun)
                    .where(SourceRun.source_id == source.id)
                    .order_by(SourceRun.started_at.desc())
                    .limit(history_limit)
                ).all()
            )
            events_next_7d = int(
                session.scalar(
                    select(func.count(Event.id)).where(
                        Event.source_id == source.id,
                        Event.status == "active",
                        Event.start_at >= current,
                        Event.start_at < freshness_end,
                    )
                )
                or 0
            )
            next_event_at = session.scalar(
                select(Event.start_at)
                .where(
                    Event.source_id == source.id,
                    Event.status == "active",
                    Event.start_at >= current,
                )
                .order_by(Event.start_at.asc())
                .limit(1)
            )

        health = _status_for_runs(
            source_name,
            runs,
            allow_empty=source_name in allow_empty_sources,
            events_next_7d=events_next_7d,
            next_event_at=next_event_at,
        )
        results[source_name] = {
            "status": health.status,
            "runs_checked": health.runs_checked,
            "latest_status": health.latest_status,
            "latest_collected": health.latest_collected,
            "median_collected": health.median_collected,
            "zero_result": health.zero_result,
            "anomaly": health.anomaly,
            "events_next_7d": health.events_next_7d,
            "next_event_at": health.next_event_at,
            "freshness_stale": health.freshness_stale,
            "message": health.message,
        }

    statuses = [item["status"] for item in results.values()]
    if any(status in {"down", "degraded"} for status in statuses):
        overall = "degraded"
    elif any(status == "unknown" for status in statuses):
        overall = "warming"
    else:
        overall = "healthy"

    return {"overall": overall, "sources": results}
