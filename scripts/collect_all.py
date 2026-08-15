import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.registry import COLLECTORS
from app.db.session import SessionLocal, init_db
from app.services.canonical_events import build_canonical_events
from app.services.data_quality import find_duplicate_candidates, validate_events
from app.services.events import apply_canonical_group_keys, upsert_events
from app.services.source_runs import finish_run, start_run

# A zero-result source is treated as a collector regression unless the source
# is explicitly known to be legitimately empty. This prevents HTTP/parsing
# failures from being silently reported as successful runs.
ALLOW_EMPTY_SOURCES = {"TicketsBox"}
QUALITY_REPORT = Path("quality-report.json")


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0, "failed": 0}
    events_by_source = {}
    quality_errors = 0
    quality_warnings = 0
    quality_issues = []

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
            quality_issues.extend(issues)
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
    canonical_events = build_canonical_events(events_by_source)
    multi_source_canonical = [event for event in canonical_events if len(event.sources) >= 2]

    with SessionLocal() as session:
        canonical_group_changes = apply_canonical_group_keys(session, canonical_events)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            source: {"collected": len(events)}
            for source, events in events_by_source.items()
        },
        "totals": totals,
        "canonical": {
            "raw_events": totals["collected"],
            "canonical_events": len(canonical_events),
            "multi_source_events": len(multi_source_canonical),
            "group_key_changes": canonical_group_changes,
            "multi_source": [
                {
                    "key": event.key,
                    "title": event.title,
                    "start_at": event.start_at,
                    "venue": event.venue,
                    "sources": [asdict(source) for source in event.sources],
                }
                for event in multi_source_canonical
            ],
        },
        "quality": {
            "invalid_events": quality_errors,
            "warnings": quality_warnings,
            "issues": [asdict(issue) for issue in quality_issues],
        },
        "duplicate_candidates": [asdict(duplicate) for duplicate in duplicates],
    }
    QUALITY_REPORT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(
        f"QUALITY SUMMARY: invalid_events={quality_errors} "
        f"warnings={quality_warnings} duplicate_candidates={len(duplicates)}"
    )
    print(
        f"CANONICAL SUMMARY: raw_events={totals['collected']} "
        f"canonical_events={len(canonical_events)} "
        f"multi_source_events={len(multi_source_canonical)} "
        f"group_key_changes={canonical_group_changes}"
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
