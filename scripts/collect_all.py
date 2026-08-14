from app.collectors.registry import COLLECTORS
from app.db.session import SessionLocal, init_db
from app.services.events import upsert_events
from app.services.source_runs import finish_run, start_run


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0, "failed": 0}

    for source_name, base_url, collect in COLLECTORS:
        with SessionLocal() as session:
            run = start_run(session, source_name, base_url)
            session.commit()

        try:
            raw_events = collect()
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
            print(f"{source_name}: collected={len(raw_events)} changed={changed}")
        except Exception as exc:
            with SessionLocal() as session:
                run = session.get(type(run), run.id)
                finish_run(session, run, status="error", error_text=str(exc))
            totals["failed"] += 1
            print(f"{source_name}: ERROR {exc}")

    print(
        f"TOTAL: collected={totals['collected']} "
        f"changed={totals['changed']} failed={totals['failed']}"
    )


if __name__ == "__main__":
    main()
