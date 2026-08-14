from app.collectors.registry import COLLECTORS
from app.db.session import SessionLocal, init_db
from app.services.events import upsert_events


def main() -> None:
    init_db()
    totals = {"collected": 0, "changed": 0}

    for source_name, base_url, collect in COLLECTORS:
        try:
            raw_events = collect()
            with SessionLocal() as session:
                changed = upsert_events(session, raw_events, source_name, base_url)
            totals["collected"] += len(raw_events)
            totals["changed"] += changed
            print(f"{source_name}: collected={len(raw_events)} changed={changed}")
        except Exception as exc:
            print(f"{source_name}: ERROR {exc}")

    print(f"TOTAL: collected={totals['collected']} changed={totals['changed']}")


if __name__ == "__main__":
    main()
