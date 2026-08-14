from datetime import datetime, timezone

from sqlalchemy import select

from app.db.models import Source, SourceRun


def start_run(session, source_name: str, base_url: str) -> SourceRun:
    source = session.scalar(select(Source).where(Source.name == source_name))
    if source is None:
        source = Source(name=source_name, base_url=base_url)
        session.add(source)
        session.flush()

    run = SourceRun(source_id=source.id)
    session.add(run)
    session.flush()
    return run


def finish_run(
    session,
    run: SourceRun,
    *,
    status: str,
    collected_count: int = 0,
    changed_count: int = 0,
    error_text: str | None = None,
) -> None:
    run.finished_at = datetime.now(timezone.utc).replace(tzinfo=None)
    run.status = status
    run.collected_count = collected_count
    run.changed_count = changed_count
    run.error_text = error_text
    session.commit()
