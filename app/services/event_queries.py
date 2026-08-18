from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher
import re

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import Event
from app.services.event_identity import normalize_title, title_without_embedded_datetime


@dataclass(slots=True)
class CanonicalDbEvent:
    representative: Event
    sources: list[Event]


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _match_title(value: str) -> str:
    return normalize_title(title_without_embedded_datetime(value))


def _title_tokens(value: str) -> set[str]:
    return set(re.findall(r"\\w+", _match_title(value), flags=re.UNICODE))


def _title_variant_match(a: Event, b: Event) -> bool:
    """Allow a source to append venue/price/ticket metadata to the same title."""
    title_a = _match_title(a.title)
    title_b = _match_title(b.title)
    if title_a == title_b:
        # Different group keys with literally identical titles are intentionally
        # kept separate: the grouping key may represent distinct source events.
        return a.group_key == b.group_key

    if SequenceMatcher(None, title_a, title_b).ratio() >= 0.90:
        return True

    short, long = sorted((_title_tokens(a.title), _title_tokens(b.title)), key=len)
    if len(short) < 3:
        return False
    # One source often appends "Тернопіль ... від 600 грн Квитки". If nearly all
    # meaningful tokens from the shorter title occur in the longer one, treat it
    # as a source variant, provided venue/time checks below also agree.
    return len(short & long) / len(short) >= 0.85


def _same_occurrence(a: Event, b: Event, time_tolerance_minutes: int = 15) -> bool:
    """Match source variants only when they describe the same occurrence."""
    if a.start_at is None or b.start_at is None:
        return False
    if abs((_utc(a.start_at) - _utc(b.start_at)).total_seconds()) > time_tolerance_minutes * 60:
        return False

    if not _title_variant_match(a, b):
        return False

    venue_a = normalize_title(a.venue.name if a.venue else "")
    venue_b = normalize_title(b.venue.name if b.venue else "")
    if venue_a and venue_b and venue_a != venue_b:
        if SequenceMatcher(None, venue_a, venue_b).ratio() < 0.80:
            return False

    return True


def events_for_day(session: Session, day: datetime) -> list[Event]:
    start = _utc(day.replace(hour=0, minute=0, second=0, microsecond=0))
    end = start + timedelta(days=1)
    return list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        ).all()
    )


def canonicalize_db_events(events: list[Event]) -> list[CanonicalDbEvent]:
    """Collapse duplicate source records but keep every distinct occurrence/time."""
    clusters: list[list[Event]] = []

    for event in events:
        matched = False
        for cluster in clusters:
            representative = cluster[0]
            # A group_key is strong evidence, but time is authoritative: two
            # showings of the same production must remain two results.
            if event.group_key == representative.group_key:
                if event.start_at is None or representative.start_at is None:
                    continue
                if abs((_utc(event.start_at) - _utc(representative.start_at)).total_seconds()) > 15 * 60:
                    continue
                cluster.append(event)
                matched = True
                break
            if _same_occurrence(event, representative):
                cluster.append(event)
                matched = True
                break
        if not matched:
            clusters.append([event])

    result: list[CanonicalDbEvent] = []
    for members in clusters:
        representative = sorted(
            members,
            key=lambda event: (
                event.start_at or datetime.max,
                -len(_match_title(event.title)),
                event.source_id,
            ),
        )[0]
        result.append(CanonicalDbEvent(representative=representative, sources=members))

    return sorted(
        result,
        key=lambda item: (item.representative.start_at or datetime.max, item.representative.title),
    )


def canonical_events_for_day(session: Session, day: datetime) -> list[CanonicalDbEvent]:
    return canonicalize_db_events(events_for_day(session, day))


def canonical_events_for_range(session: Session, start: datetime, end: datetime) -> list[CanonicalDbEvent]:
    start = _utc(start)
    end = _utc(end)
    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        ).all()
    return canonicalize_db_events(events)


def category_counts(session: Session, start: datetime, end: datetime) -> list[tuple[str, int]]:
    """Count distinct displayed occurrences, not raw source rows."""
    events = canonical_events_for_range(session, start, end)
    counts = Counter((item.representative.category or "Інше") for item in events)
    return sorted(counts.items(), key=lambda item: (-item[1], item[0]))


def canonical_events_for_category(
    session: Session, category: str, start: datetime, end: datetime
) -> list[CanonicalDbEvent]:
    start = _utc(start)
    end = _utc(end)
    events = list(
        session.scalars(
            select(Event)
            .options(selectinload(Event.venue))
            .where(
                Event.start_at >= start,
                Event.start_at < end,
                Event.status == "active",
            )
            .order_by(Event.start_at, Event.title)
        ).all()
    canonical = canonicalize_db_events(events)
    return [
        item
        for item in canonical
        if (item.representative.category or "Інше") == category
    ]
