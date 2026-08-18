from datetime import datetime
from types import SimpleNamespace
from zoneinfo import ZoneInfo

from app.bot.handlers import _format_event


def test_format_event_contains_separate_date_and_time_and_cleans_embedded_date():
    event = SimpleNamespace(
        title="Лос Янковерс. Колумбійці, які співають українські пісні 9 вересня 2026 18:00",
        start_at=datetime(2026, 9, 9, 15, 0, tzinfo=ZoneInfo("UTC")),
        venue=SimpleNamespace(name="Тернопільський театр"),
        price_text="300 грн",
    )
    item = SimpleNamespace(representative=event, sources=[event])
    text = _format_event(item)

    assert "Лос Янковерс. Колумбійці, які співають українські пісні" in text
    assert "9 вересня 2026 18:00" not in text
    assert "📅 09.09.2026" in text
    assert "🕐 18:00" in text
    assert "Тернопільський театр" in text
    assert "300 грн" in text
