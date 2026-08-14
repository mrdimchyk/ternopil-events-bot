from app.collectors.karabas import collect, BASE_URL
from app.db.session import SessionLocal, init_db
from app.services.events import upsert_events

if __name__ == "__main__":
    init_db()
    events = collect()
    with SessionLocal() as session:
        inserted = upsert_events(session, events, "KARABAS", BASE_URL)
    print(f"Collected: {len(events)}; inserted/updated: {inserted}")
