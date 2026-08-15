from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from app.collectors.base import RawEvent
from app.services.event_identity import make_group_key, normalize_title


@dataclass(slots=True)
class CanonicalSource:
    source: str
    external_id: str
    source_url: str
    ticket_url: str | None
    price_text: str | None


@dataclass(slots=True)
class CanonicalEvent:
    key: str
    title: str
    start_at: datetime | None
    venue: str | None
    address: str | None
    category: str | None
    description: str | None
    sources: list[CanonicalSource]


def _same_event(a: RawEvent, b: RawEvent, time_tolerance_minutes: int = 15) -> bool:
    if a.start_at is None or b.start_at is None:
        return False
    if abs((a.start_at - b.start_at).total_seconds()) > time_tolerance_minutes * 60:
        return False
    return SequenceMatcher(None, normalize_title(a.title), normalize_title(b.title)).ratio() >= 0.90


def build_canonical_events(events_by_source: dict[str, list[RawEvent]]) -> list[CanonicalEvent]:
    clusters: list[list[tuple[str, RawEvent]]] = []

    for source, events in events_by_source.items():
        for event in events:
            for cluster in clusters:
                if _same_event(event, cluster[0][1]):
                    cluster.append((source, event))
                    break
            else:
                clusters.append([(source, event)])

    result: list[CanonicalEvent] = []
    for cluster in clusters:
        ordered = sorted(cluster, key=lambda item: (len(item[1].title), item[1].title), reverse=True)
        representative = ordered[0][1]
        start_at = min((event.start_at for _, event in cluster if event.start_at is not None), default=None)
        key_basis = make_group_key(representative.title, start_at, representative.venue)

        result.append(
            CanonicalEvent(
                key=key_basis,
                title=representative.title,
                start_at=start_at,
                venue=representative.venue,
                address=representative.address,
                category=representative.category,
                description=representative.description,
                sources=[
                    CanonicalSource(
                        source=source,
                        external_id=event.external_id,
                        source_url=event.source_url,
                        ticket_url=event.ticket_url,
                        price_text=event.price_text,
                    )
                    for source, event in sorted(cluster, key=lambda item: item[0])
                ],
            )
        )

    return result
