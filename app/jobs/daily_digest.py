from datetime import datetime

from app.db.session import SessionLocal
from app.services.notifications import tomorrow_events, users_for_tomorrow


def build_tomorrow_digest(now: datetime | None = None) -> str:
    with SessionLocal() as session:
        events = tomorrow_events(session, now)
    if not events:
        return "🌙 <b>Завтра в Тернополі</b>\n\nПоки що цікавих подій у базі немає."

    lines = ["🌙 <b>Що цікавого завтра в Тернополі</b>", ""]
    for event in events[:15]:
        time = event.start_at.strftime("%H:%M") if event.start_at else "час уточнюється"
        price = f" · {event.price_text}" if event.price_text else ""
        lines.append(f"🎟️ <b>{event.title}</b> — {time}{price}")
        if event.ticket_url:
            lines.append(f"🎫 {event.ticket_url}")
        lines.append("")
    return "\n".join(lines).strip()
