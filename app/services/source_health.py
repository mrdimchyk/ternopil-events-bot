from dataclasses import dataclass
from statistics import median

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Source, SourceRun


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
    message: str


def _status_for_runs(
    source_name: str,
    runs: list[SourceRun],
    *,
    allow_empty: bool,
    minimum_runs: int = 3,
) -> SourceHealth:
    latest = runs[0] if runs else None
    counts = [run.collected_count for run in runs if run.status == "success"]
    latest_count = latest.collected_count if latest else None
    zero_result = bool(latest and latest.status == "success" and latest_count == 0 and not allow_empty)

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
    elif len(runs) < minimum_runs:
        status = "warming"
        message = f"Only {len(runs)} run(s) available; anomaly baseline is still warming up."
    else:
        status = "healthy"
        message = "Recent collection results are within the expected range."

    return SourceHealth(
        source=source_name,
        status=status,
        runs_checked=len(runs),
        latest_status=latest.status if latest else None,
        latest_collected=latest_count,
        median_collected=float(baseline) if baseline is not None else None,
        zero_result=zero_result,
        anomaly=anomaly,
        message=message,
    )


def source_health_report(
    session: Session,
    source_names: list[str],
    *,
    allow_empty_sources: set[str] | None = None,
    history_limit: int = 7,
) -> dict[str, object]:
    allow_empty_sources = allow_empty_sources or set()
    results: dict[str, dict[str, object]] = {}

    for source_name in source_names:
        source = session.scalar(select(Source).where(Source.name == source_name))
        runs = []
        if source is not None:
            runs = list(
                session.scalars(
                    select(SourceRun)
                    .where(SourceRun.source_id == source.id)
                    .order_by(SourceRun.started_at.desc())
                    .limit(history_limit)
                ).all()
            )
        health = _status_for_runs(
            source_name,
            runs,
            allow_empty=source_name in allow_empty_sources,
        )
        results[source_name] = {
            "status": health.status,
            "runs_checked": health.runs_checked,
            "latest_status": health.latest_status,
            "latest_collected": health.latest_collected,
            "median_collected": health.median_collected,
            "zero_result": health.zero_result,
            "anomaly": health.anomaly,
            "message": health.message,
        }

    statuses = [item["status"] for item in results.values()]
    if any(status == "down" for status in statuses):
        overall = "degraded"
    elif any(status == "degraded" for status in statuses):
        overall = "degraded"
    elif any(status == "unknown" for status in statuses):
        overall = "warming"
    else:
        overall = "healthy"

    return {"overall": overall, "sources": results}
