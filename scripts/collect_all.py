from datetime import datetime, timezone

from app.collectors.registry import COLLECTORS
from app.db.session import SessionLocal, init_db
from app.services.data_quality import find_duplicate_candidates, validate_events
from app.services.events import upsert_events
from app.services.source_runs import finish_run, start_run

# A zero-result source is treated as a collector regression unless the source
# is explicitly known to be legitimately empty. This prevents HTTP/parsing
# failures from being silently reported as successful runs.
ALLOW_EMPTY_SOURCES = {"TicketsBox"}


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0, "failed": 0}
    events_by_source = {}
    quality_errors = 0
    quality_warnings = 0

    for source_name, base_url, collect in COLLECTORS:
        with SessionLocal() as session:
            run = start_run(session, source_name, base_url)
            session.commit()

        try:
            raw_events = collect()
            events_by_source[source_name] = raw_events
            if not raw_events and source_name not in ALLOW_EMPTY_SOURCES:
                raise RuntimeError(
                    "Collector returned zero events for a source expected to contain "
                    "current Ternopil events; inspect the source/parser before accepting the run."
                )

            issues = validate_events(
                source_name,
                raw_events,
                now=datetime.now(timezone.utc),
            )
            errors = [issue for issue in issues if issue.severity == "error"]
            warnings = [issue for issue in issues if issue.severity == "warning"]
            quality_errors += len(errors)
            quality_warnings += len(warnings)
            for issue in issues:
                print(
                    f"QUALITY {issue.severity.upper()}: {issue.source_name} "
                    f"{issue.code}: {issue.message}"
                )
            if errors:
                raise RuntimeError(
                    f"Data quality rejected {source_name}: {len(errors)} invalid event(s)."
                )

            with SessionLocal() as session:
                changed = upsert_events(session, raw_events, source_name, base_url)
                run = session.get(type(run), run.id)
                finish_run(
                    session,
                    run,
                    status="success",
                    collected_count=len(raw_events),
                    changed_count=changed,
                )
            totals["collected"] += len(raw_events)
            totals["changed"] += changed
            print(
                f"{source_name}: collected={len(raw_events)} "
                f"changed={changed} quality_errors={len(errors)} "
                f"quality_warnings={len(warnings)}"
            )
        except Exception as exc:
            with SessionLocal() as session:
                run = session.get(type(run), run.id)
                finish_run(
                    session,
                    run,
                    status="error",
                    error_text=str(exc),
                )
            totals["failed"] += 1
            print(f"{source_name}: ERROR {exc}")

    duplicates = find_duplicate_candidates(events_by_source)
    print(
        f"QUALITY SUMMARY: invalid_events={quality_errors} "
        f"warnings={quality_warnings} duplicate_candidates={len(duplicates)}"
    )
    for duplicate in duplicates:
        print(
            "DUPLICATE CANDIDATE: "
            f"sources={','.join(duplicate.sources)} "
            f"start_at={duplicate.start_at} "
            f"titles={' | '.join(duplicate.titles)}"
        )

    print(
        f"TOTAL: collected={totals['collected']} "
        f"changed={totals['changed']} failed={totals['failed']}"
    )

    if totals["failed"] or quality_errors:
        raise RuntimeError(
            f"Collection completed with {totals['failed']} source failure(s) and "
            f"{quality_errors} data-quality error(s); do not treat the run as healthy."
        )


if __name__ == "__main__":
    main()
