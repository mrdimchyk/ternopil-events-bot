from app.collectors.karabas import BASE_URL, collect
from app.db.session import SessionLocal, init_db
from app.services.events import upsert_events


def main() -> None:
    init_db()
    raw_events = collect()
    with SessionLocal() as session:
        created = upsert_events(session, raw_events, "KARABAS", BASE_URL)
    print(f"KARABAS: collected={len(raw_events)} created={created}")


if __name__ == "__main__":
    main()
