from datetime import datetime, timedelta, timezone
from html import escape
from zoneinfo import ZoneInfo

from app.config import settings
from app.db.session import SessionLocal
from app.services.notifications import tomorrow_events
from app.services.event_identity import title_without_embedded_datetime


def build_tomorrow_digest(now: datetime | None = None) -> str:
    city_timezone = ZoneInfo(settings.timezone)
    current = now or datetime.now(timezone.utc)
    local_now = (current.astimezone(city_timezone) if current.tzinfo
                 else current.replace(tzinfo=city_timezone))
    date_label = (local_now.date() + timedelta(days=1)).strftime("%d.%m.%Y")
    with SessionLocal() as session:
        events = tomorrow_events(session, current)
    if not events:
        return (f"🌙 <b>Завтра в Тернополі</b> · {date_label}\n\n"
                "Поки що цікавих подій у базі немає.")

    lines = [f"🌙 <b>Що цікавого завтра в Тернополі</b> · {date_label}", ""]
    for event in events[:15]:
        start = event.start_at
        if start is not None:
            # Naive DB values (SQLite and legacy drivers) represent UTC, too.
            start = start.replace(tzinfo=timezone.utc) if start.tzinfo is None else start
            time = start.astimezone(city_timezone).strftime("%H:%M")
        else:
            time = "час уточнюється"
        price = f" · {escape(event.price_text)}" if event.price_text else ""
        title = escape(title_without_embedded_datetime(event.title))
        lines.append(f"🎟️ <b>{title}</b> — {time}{price}")
        if event.ticket_url:
            lines.append(f"🎫 {escape(event.ticket_url)}")
        lines.append("")
    return "\n".join(lines).strip()
