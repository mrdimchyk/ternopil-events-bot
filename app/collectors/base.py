from dataclasses import dataclass
from datetime import datetime

@dataclass(slots=True)
class RawEvent:
    external_id: str
    title: str
    category: str | None
    start_at: datetime | None
    venue: str | None
    address: str | None
    price_text: str | None
    ticket_url: str | None
    source_url: str
    description: str | None = None
