from datetime import datetime, timezone

from sqlalchemy import select

from app.collectors.base import RawEvent
from app.db.models import Event, EventChange, Source, Venue
from app.services.canonical_events import CanonicalEvent
from app.services.event_identity import make_group_key


def _record_change(session, event_id: int, change_type: str, field_name: str | None = None,
                   old_value: str | None = None, new_value: str | None = None) -> None:
    session.add(EventChange(
        event_id=event_id,
        change_type=change_type,
        field_name=field_name,
        old_value=old_value,
        new_value=new_value,
    ))


def upsert_events(session, raw_events: list[RawEvent], source_name: str, base_url: str) -> int:
    source = session.scalar(select(Source).where(Source.name == source_name))
    if not source:
        source = Source(name=source_name, base_url=base_url)
        session.add(source)
        session.flush()

    changed = 0
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    for raw in raw_events:
        event = session.scalar(select(Event).where(
            Event.source_id == source.id,
            Event.external_id == raw.external_id,
        ))

        venue = None
        if raw.venue:
            venue = session.scalar(select(Venue).where(Venue.name == raw.venue))
            if not venue:
                venue = Venue(name=raw.venue, address=raw.address)
                session.add(venue)
                session.flush()

        group_key = make_group_key(raw.title, raw.start_at, raw.venue)

        if event is None:
            event = Event(
                external_id=raw.external_id,
                group_key=group_key,
                source_id=source.id,
                title=raw.title,
                category=raw.category,
                start_at=raw.start_at,
                venue_id=venue.id if venue else None,
                price_text=raw.price_text,
                ticket_url=raw.ticket_url,
                source_url=raw.source_url,
                description=raw.description,
                first_seen_at=now,
                last_seen_at=now,
            )
            session.add(event)
            session.flush()
            _record_change(session, event.id, "event_created")
            changed += 1
            continue

        tracked = {
            "group_key": (event.group_key, group_key),
            "title": (event.title, raw.title),
            "category": (event.category, raw.category),
            "start_at": (event.start_at, raw.start_at),
            "price_text": (event.price_text, raw.price_text),
            "ticket_url": (event.ticket_url, raw.ticket_url),
        }

        for field_name, (old, new) in tracked.items():
            old_text = old.isoformat() if isinstance(old, datetime) else (str(old) if old is not None else None)
            new_text = new.isoformat() if isinstance(new, datetime) else (str(new) if new is not None else None)
            if old_text == new_text:
                continue

            if field_name == "group_key":
                setattr(event, field_name, new)
                continue
            if field_name == "ticket_url":
                if not old and new:
                    _record_change(session, event.id, "ticket_sale_started", field_name, old_text, new_text)
                elif old and not new:
                    _record_change(session, event.id, "ticket_link_removed", field_name, old_text, new_text)
                else:
                    _record_change(session, event.id, "ticket_link_changed", field_name, old_text, new_text)
            elif field_name == "price_text":
                _record_change(session, event.id, "price_changed", field_name, old_text, new_text)
            elif field_name == "start_at":
                _record_change(session, event.id, "date_changed", field_name, old_text, new_text)
            else:
                _record_change(session, event.id, "field_changed", field_name, old_text, new_text)

            setattr(event, field_name, new)
            changed += 1

        event.source_url = raw.source_url
        event.description = raw.description
        event.last_seen_at = now
        if venue:
            event.venue_id = venue.id

    session.commit()
    return changed


def apply_canonical_group_keys(session, canonical_events: list[CanonicalEvent]) -> int:
    """Assign one group_key to every source record in multi-source canonical clusters."""
    changed = 0
    for canonical in canonical_events:
        if len(canonical.sources) < 2:
            continue
        for source_ref in canonical.sources:
            source = session.scalar(select(Source).where(Source.name == source_ref.source))
            if not source:
                continue
            event = session.scalar(select(Event).where(
                Event.source_id == source.id,
                Event.external_id == source_ref.external_id,
            ))
            if event and event.group_key != canonical.key:
                old_key = event.group_key
                event.group_key = canonical.key
                _record_change(
                    session,
                    event.id,
                    "canonical_group_assigned",
                    "group_key",
                    old_key,
                    canonical.key,
                )
                changed += 1
    session.commit()
    return changed
