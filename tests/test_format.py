from types import SimpleNamespace

from app.bot.handlers import _format_event


def test_format_event_contains_core_fields():
    event = SimpleNamespace(
        title="Тестова подія",
        start_at=SimpleNamespace(strftime=lambda fmt: "19:00"),
        venue=SimpleNamespace(name="Тернопільський театр"),
        price_text="300 грн",
    )
    item = SimpleNamespace(representative=event, sources=[event])
    text = _format_event(item)
    assert "Тестова подія" in text
    assert "19:00" in text
    assert "Тернопільський театр" in text
    assert "300 грн" in text
