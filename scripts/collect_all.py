from app.collectors.registry import COLLECTORS
from app.db.session import SessionLocal, init_db
from app.services.events import upsert_events
from app.services.source_runs import finish_run, start_run

# A zero-result source is treated as a collector regression unless the source
# is explicitly known to be legitimately empty. This prevents HTTP/parsing
# failures from being silently reported as successful runs.
ALLOW_EMPTY_SOURCES = {"TicketsBox"}


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0, "failed": 0}

    for source_name, base_url, collect in COLLECTORS:
        with SessionLocal() as session:
            run = start_run(session, source_name, base_url)
            session.commit()

        try:
            raw_events = collect()
            if not raw_events and source_name not in ALLOW_EMPTY_SOURCES:
                raise RuntimeError(
                    "Collector returned zero events for a source expected to contain "
                    "current Ternopil events; inspect the source/parser before accepting the run."
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
                f"changed={changed}"
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

    print(
        f"TOTAL: collected={totals['collected']} "
        f"changed={totals['changed']} failed={totals['failed']}"
    )

    if totals["failed"]:
        raise RuntimeError(
            f"Collection completed with {totals['failed']} source failure(s); "
            "do not treat the run as healthy."
        )


if __name__ == "__main__":
    main()
