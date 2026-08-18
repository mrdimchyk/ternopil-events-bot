import hashlib
import re
import unicodedata
from datetime import datetime
from difflib import SequenceMatcher

MONTHS_UK = {
    "січня": 1, "лютого": 2, "березня": 3, "квітня": 4,
    "травня": 5, "червня": 6, "липня": 7, "серпня": 8,
    "вересня": 9, "жовтня": 10, "листопада": 11, "грудня": 12,
}
MONTH_PATTERN_UK = "(?:" + "|".join(MONTHS_UK) + ")"
EVENT_DATETIME_RE = re.compile(
    rf"(?P<day>\d{{1,2}})\s+(?P<month>{MONTH_PATTERN_UK})"
    rf"(?:\s+(?P<year>20\d{{2}}))?"
    rf"(?:\s*(?:,|\||—|-)?\s*(?P<hour>\d{{1,2}}):(?P<minute>\d{{2}}))?",
    re.IGNORECASE,
)


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_datetime_from_text(text: str, *, default_year: int | None = None) -> datetime | None:
    """Extract a Ukrainian date/time from free text when a collector missed it."""
    if not text:
        return None
    match = EVENT_DATETIME_RE.search(text)
    if not match:
        return None
    values = match.groupdict()
    try:
        explicit_year = values["year"] is not None
        year = int(values["year"] or default_year or datetime.now().year)
        hour = int(values["hour"] or 0)
        minute = int(values["minute"] or 0)
        value = datetime(year, MONTHS_UK[values["month"].lower()], int(values["day"]), hour, minute)
        if not explicit_year and value < datetime.now():
            value = value.replace(year=value.year + 1)
        return value
    except (KeyError, TypeError, ValueError):
        return None


def _strip_source_metadata(text: str) -> str:
    """Remove common ticket/source suffixes appended to scraped event titles."""
    patterns = (
        r"\s+\bтернопіль\b.*$",
        r"\s+\bквитки\b.*$",
        r"\s+\bвід\s+\d+(?:[.,]\d+)?\s*(?:грн|₴|uah)?\b.*$",
        r"\s+\b\d+(?:[.,]\d+)?\s*(?:грн|₴|uah)\b.*$",
    )
    cleaned = text
    for pattern in patterns:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
    return cleaned


def title_without_embedded_datetime(title: str) -> str:
    """Remove embedded date/time and common scraped source metadata from a title."""
    cleaned = EVENT_DATETIME_RE.sub(" ", title or "")
    cleaned = _strip_source_metadata(cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    # Keep the conventional separator spacing in titles such as "Artist | Event".
    # Pipe is semantic title content, not punctuation whose leading whitespace
    # should be stripped.
    cleaned = re.sub(r"\s+([,:])", r"\1", cleaned)
    cleaned = re.sub(r"([,|])\s*$", "", cleaned)
    return cleaned.strip(" -—|,:") or (title or "")


def title_variant_match(title_a: str, title_b: str) -> bool:
    """Match source title variants while rejecting unrelated short titles."""
    normalized_a = normalize_title(title_without_embedded_datetime(title_a))
    normalized_b = normalize_title(title_without_embedded_datetime(title_b))
    if normalized_a == normalized_b:
        return True
    if SequenceMatcher(None, normalized_a, normalized_b).ratio() >= 0.90:
        return True

    tokens_a = set(re.findall(r"\w+", normalized_a, flags=re.UNICODE))
    tokens_b = set(re.findall(r"\w+", normalized_b, flags=re.UNICODE))
    short, long = sorted((tokens_a, tokens_b), key=len)
    if len(short) < 3:
        return False
    return len(short & long) / len(short) >= 0.85


def make_group_key(title: str, start_at: datetime | None, venue: str | None) -> str:
    date_part = start_at.strftime("%Y-%m-%d-%H-%M") if start_at else "unknown-time"
    venue_part = normalize_title(venue or "")
    raw = f"{normalize_title(title_without_embedded_datetime(title))}|{date_part}|{venue_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]
