import hashlib
import re
import unicodedata
from datetime import datetime


def normalize_title(title: str) -> str:
    text = unicodedata.normalize("NFKC", title).lower()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_group_key(title: str, start_at: datetime | None, venue: str | None) -> str:
    date_part = start_at.strftime("%Y-%m-%d-%H-%M") if start_at else "unknown-time"
    venue_part = normalize_title(venue or "")
    raw = f"{normalize_title(title)}|{date_part}|{venue_part}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]
