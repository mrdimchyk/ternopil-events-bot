import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from app.collectors.registry import COLLECTORS, source_tier
from app.db.session import SessionLocal, init_db
from app.services.canonical_events import build_canonical_events
from app.services.collection_policy import ALLOW_EMPTY_SOURCES, collection_should_fail
from app.services.data_quality import enrich_missing_start_at, find_duplicate_candidates, validate_events
from app.services.events import apply_canonical_group_keys, upsert_events
from app.services.source_field_coverage import source_field_coverage
from app.services.source_health import source_health_report
from app.services.source_runs import finish_run, start_run
from app.services.source_value import source_value_metrics

QUALITY_REPORT = Path("quality-report.json")


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0, "failed": 0, "core_failed": 0}
    events_by_source = {}
    failures = []
    quality_errors = 0
    quality_warnings = 0
    quality_issues = []
    repaired_dates = 0

    for source_name, base_url, collect in COLLECTORS:
        tier = source_tier(source_name)
        with SessionLocal() as session:
            run = start_run(session, source_name, base_url)
            session.commit()

        try:
            raw_events = collect()
            repaired = enrich_missing_start_at(raw_events, default_year=datetime.now().year)
            repaired_dates += repaired
            events_by_source[source_name] = raw_events
            if not raw_events and source_name not in ALLOW_EMPTY_SOURCES:
                raise RuntimeError(
                    "Collector returned zero events for a source expected to contain "
                    "current Ternopil events; inspect the source/parser before accepting the run."
                )

            issues = validate_events(source_name, raw_events, now=datetime.now(timezone.utc))
            quality_issues.extend(issues)
            errors = [issue for issue in issues if issue.severity == "error"]
            warnings = [issue for issue in issues if issue.severity == "warning"]
            quality_errors += len(errors)
            quality_warnings += len(warnings)
            for issue in issues:
                print(f"QUALITY {issue.severity.upper()}: {issue.source_name} {issue.code}: {issue.message}")
            if errors:
                raise RuntimeError(f"Data quality rejected {source_name}: {len(errors)} invalid event(s).")

            with SessionLocal() as session:
                changed = upsert_events(session, raw_events, source_name, base_url)
                run = session.get(type(run), run.id)
                finish_run(session, run, status="success", collected_count=len(raw_events), changed_count=changed)
            totals["collected"] += len(raw_events)
            totals["changed"] += changed
            print(f"{source_name}: tier={tier} collected={len(raw_events)} changed={changed} repaired_dates={repaired} quality_errors={len(errors)} quality_warnings={len(warnings)}")
        except Exception as exc:
            with SessionLocal() as session:
                run = session.get(type(run), run.id)
                finish_run(session, run, status="error", error_text=str(exc))
            totals["failed"] += 1
            if tier == "core":
                totals["core_failed"] += 1
            failures.append({"source": source_name, "tier": tier, "error": str(exc)})
            print(f"{source_name}: tier={tier} ERROR {exc}")

    source_names = [source_name for source_name, _, _ in COLLECTORS]
    core_source_names = {source_name for source_name in source_names if source_tier(source_name) == "core"}
    with SessionLocal() as session:
        health = source_health_report(
            session,
            source_names,
            allow_empty_sources=ALLOW_EMPTY_SOURCES,
            overall_source_names=core_source_names,
        )

    duplicates = find_duplicate_candidates(events_by_source)
    canonical_events = build_canonical_events(events_by_source)
    multi_source_canonical = [event for event in canonical_events if len(event.sources) >= 2]
    source_value = source_value_metrics(canonical_events, source_names)
    field_coverage = source_field_coverage(events_by_source, source_names)

    with SessionLocal() as session:
        canonical_group_changes = apply_canonical_group_keys(session, canonical_events)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sources": {
            source: {
                "collected": len(events),
                "tier": source_tier(source),
                "value": asdict(source_value[source]),
                "field_coverage": asdict(field_coverage[source]),
                **health["sources"].get(source, {}),
            }
            for source, events in events_by_source.items()
        },
        "source_health": health,
        "failures": failures,
        "totals": totals,
        "canonical": {
            "raw_events": totals["collected"],
            "canonical_events": len(canonical_events),
            "multi_source_events": len(multi_source_canonical),
            "group_key_changes": canonical_group_changes,
            "multi_source": [
                {"key": event.key, "title": event.title, "start_at": event.start_at, "venue": event.venue, "sources": [asdict(source) for source in event.sources]}
                for event in multi_source_canonical
            ],
        },
        "source_value": {source: asdict(value) for source, value in source_value.items()},
        "source_field_coverage": {source: asdict(value) for source, value in field_coverage.items()},
        "quality": {"invalid_events": quality_errors, "warnings": quality_warnings, "repaired_dates": repaired_dates, "issues": [asdict(issue) for issue in quality_issues]},
        "duplicate_candidates": [asdict(duplicate) for duplicate in duplicates],
    }
    QUALITY_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str), encoding="utf-8")

    print(f"QUALITY SUMMARY: invalid_events={quality_errors} warnings={quality_warnings} repaired_dates={repaired_dates} duplicate_candidates={len(duplicates)}")
    print(f"SOURCE HEALTH: overall={health['overall']}")
    for source, item in health["sources"].items():
        print(f"SOURCE HEALTH: {source} tier={source_tier(source)} status={item['status']} latest_collected={item['latest_collected']} median_collected={item['median_collected']} events_next_7d={item['events_next_7d']} next_event_at={item['next_event_at']} freshness_stale={item['freshness_stale']} message={item['message']}")
    print(f"CANONICAL SUMMARY: raw_events={totals['collected']} canonical_events={len(canonical_events)} multi_source_events={len(multi_source_canonical)} group_key_changes={canonical_group_changes}")
    for source in source_names:
        value = source_value[source]
        print(
            f"SOURCE VALUE: {source} tier={source_tier(source)} "
            f"canonical={value.canonical_events} unique={value.unique_events} "
            f"shared={value.shared_events} overlap_ratio={value.overlap_ratio:.3f} "
            f"unique_coverage_ratio={value.unique_coverage_ratio:.3f}"
        )
    for source in source_names:
        fields = field_coverage[source]
        print(
            f"SOURCE FIELDS: {source} events={fields.event_count} "
            f"start={fields.start_at_ratio:.3f} venue={fields.venue_ratio:.3f} "
            f"address={fields.address_ratio:.3f} price={fields.price_ratio:.3f} "
            f"ticket={fields.ticket_url_ratio:.3f} description={fields.description_ratio:.3f}"
        )
    for duplicate in duplicates:
        print("DUPLICATE CANDIDATE: " f"sources={','.join(duplicate.sources)} " f"start_at={duplicate.start_at} " f"titles={' | '.join(duplicate.titles)}")

    print(f"TOTAL: collected={totals['collected']} changed={totals['changed']} failed={totals['failed']} core_failed={totals['core_failed']}")

    if collection_should_fail(core_failures=totals["core_failed"], quality_errors=quality_errors):
        raise RuntimeError(
            f"Collection completed with {totals['core_failed']} core source failure(s), "
            f"{totals['failed'] - totals['core_failed']} isolated non-core failure(s), "
            f"{quality_errors} data-quality error(s), source_health={health['overall']}."
        )


if __name__ == "__main__":
    main()
