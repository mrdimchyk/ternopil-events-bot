from dataclasses import dataclass

from app.services.canonical_events import CanonicalEvent


@dataclass(frozen=True, slots=True)
class SourceValue:
    canonical_events: int
    unique_events: int
    shared_events: int
    overlap_ratio: float
    unique_coverage_ratio: float


def source_value_metrics(
    canonical_events: list[CanonicalEvent], source_names: list[str]
) -> dict[str, SourceValue]:
    """Measure marginal canonical coverage contributed by each source."""
    total = len(canonical_events)
    counts = {
        source: {"canonical": 0, "unique": 0, "shared": 0}
        for source in source_names
    }

    for event in canonical_events:
        sources = {item.source for item in event.sources}
        for source in sources:
            if source not in counts:
                counts[source] = {"canonical": 0, "unique": 0, "shared": 0}
            counts[source]["canonical"] += 1
            if len(sources) == 1:
                counts[source]["unique"] += 1
            else:
                counts[source]["shared"] += 1

    result: dict[str, SourceValue] = {}
    for source, item in counts.items():
        canonical = item["canonical"]
        result[source] = SourceValue(
            canonical_events=canonical,
            unique_events=item["unique"],
            shared_events=item["shared"],
            overlap_ratio=(item["shared"] / canonical) if canonical else 0.0,
            unique_coverage_ratio=(item["unique"] / total) if total else 0.0,
        )
    return result
