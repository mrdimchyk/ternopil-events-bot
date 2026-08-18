from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from urllib.parse import urlparse

from app.collectors.base import RawEvent
from app.services.event_identity import extract_datetime_from_text, normalize_title


@dataclass(slots=True)
class QualityIssue:
    source_name: str
    external_id: str
    severity: str
    code: str
    message: str


@dataclass(slots=True)
class DuplicateCandidate:
    sources: tuple[str, ...]
    titles: tuple[str, ...]
    start_at: datetime | None
    event_ids: tuple[str, ...]


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def enrich_missing_start_at(events: list[RawEvent], *, default_year: int | None = None) -> int:
    """Recover a missing event date/time from the title before quality validation."""
    repaired = 0
    for event in events:
        if event.start_at is not None:
            continue
        extracted = extract_datetime_from_text(event.title, default_year=default_year)
        if extracted is None:
            continue
        event.start_at = extracted
        repaired += 1
    return repaired


def validate_events(
    source_name: str,
    events: list[RawEvent],
    *,
    now: datetime | None = None,
) -> list[QualityIssue]:
    now = _naive(now or datetime.now(timezone.utc))
    issues: list[QualityIssue] = []

    for event in events:
        prefix = (source_name, event.external_id)
        if not event.external_id.strip():
            issues.append(QualityIssue(*prefix, "error", "missing_external_id", "external_id is empty"))
        if not event.title.strip():
            issues.append(QualityIssue(*prefix, "error", "missing_title", "title is empty"))
        if not event.source_url.strip():
            issues.append(QualityIssue(*prefix, "error", "missing_source_url", "source_url is empty"))
        elif urlparse(event.source_url).scheme not in {"http", "https"}:
            issues.append(QualityIssue(*prefix, "error", "invalid_source_url", "source_url is not HTTP(S)"))

        start_at = _naive(event.start_at)
        if start_at is None:
            issues.append(QualityIssue(*prefix, "error", "missing_start_at", "start_at is missing"))
        elif start_at < now:
            issues.append(QualityIssue(*prefix, "error", "past_event", "event is already in the past"))

        if event.ticket_url and urlparse(event.ticket_url).scheme not in {"http", "https"}:
            issues.append(QualityIssue(*prefix, "warning", "invalid_ticket_url", "ticket_url is not HTTP(S)"))

    return issues


def find_duplicate_candidates(
    events_by_source: dict[str, list[RawEvent]],
    *,
    time_tolerance_minutes: int = 15,
    title_similarity: float = 0.90,
) -> list[DuplicateCandidate]:
    flattened = [
        (source, event)
        for source, events in events_by_source.items()
        for event in events
    ]
    candidates: list[DuplicateCandidate] = []
    seen: set[frozenset[str]] = set()

    for index, (source_a, event_a) in enumerate(flattened):
        start_a = _naive(event_a.start_at)
        if start_a is None:
            continue
        title_a = normalize_title(event_a.title)
        for source_b, event_b in flattened[index + 1 :]:
            if source_a == source_b:
                continue
            start_b = _naive(event_b.start_at)
            if start_b is None:
                continue
            if abs((start_a - start_b).total_seconds()) > time_tolerance_minutes * 60:
                continue
            title_b = normalize_title(event_b.title)
            if SequenceMatcher(None, title_a, title_b).ratio() < title_similarity:
                continue

            key = frozenset({event_a.external_id, event_b.external_id})
            if key in seen:
                continue
            seen.add(key)
            candidates.append(
                DuplicateCandidate(
                    sources=tuple(sorted({source_a, source_b})),
                    titles=(event_a.title, event_b.title),
                    start_at=start_a,
                    event_ids=(event_a.external_id, event_b.external_id),
                )
            )

    return candidates


def quality_summary(
    events_by_source: dict[str, list[RawEvent]],
    issues: list[QualityIssue],
    duplicates: list[DuplicateCandidate],
) -> dict[str, object]:
    errors_by_source = defaultdict(int)
    warnings_by_source = defaultdict(int)
    for issue in issues:
        target = errors_by_source if issue.severity == "error" else warnings_by_source
        target[issue.source_name] += 1

    return {
        "sources": {
            source: {
                "collected": len(events),
                "errors": errors_by_source[source],
                "warnings": warnings_by_source[source],
            }
            for source, events in events_by_source.items()
        },
        "invalid_events": sum(errors_by_source.values()),
        "warnings": sum(warnings_by_source.values()),
        "duplicate_candidates": len(duplicates),
    }
