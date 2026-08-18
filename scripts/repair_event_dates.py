from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import settings
from app.db.models import Event
from app.db.session import SessionLocal, init_db
from app.services.event_identity import extract_datetime_from_text, make_group_key


def main() -> None:
    init_db()
    now = datetime.now(timezone.utc)
    repaired = 0

    with SessionLocal() as session:
        events = list(
            session.scalars(
                select(Event)
                .where(Event.start_at.is_(None), Event.status == "active")
                .order_by(Event.id)
            ).all()
        )

        for event in events:
            extracted = extract_datetime_from_text(event.title, default_year=now.astimezone(ZoneInfo(settings.timezone)).year)
            if extracted is None:
                continue
            normalized = extracted.replace(tzinfo=ZoneInfo(settings.timezone)).astimezone(timezone.utc)
            event.start_at = normalized
            venue_name = event.venue.name if event.venue else None
            event.group_key = make_group_key(event.title, normalized, venue_name)
            repaired += 1

        session.commit()

    print(f"REPAIRED EVENT DATES: {repaired}")


if __name__ == "__main__":
    main()
