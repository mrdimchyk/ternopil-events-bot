from datetime import datetime

from app.collectors.teatr_org_ua import (
    _event_urls,
    _future_city_events,
    _markdown_city_events,
    _tour_urls,
)


def test_event_urls_from_jina_markdown():
    text = "[Я бачу, вас цікавить пітьма](https://teatr.org.ua/events/ia-bacu-vas-cikavit-pitma-08-10-2026-18-00)"
    assert _event_urls(text, "https://teatr.org.ua/cities/ternopil") == [
        "https://teatr.org.ua/events/ia-bacu-vas-cikavit-pitma-08-10-2026-18-00"
    ]


def test_tour_urls_from_jina_markdown():
    text = "[Я бачу, вас цікавить пітьма](https://teatr.org.ua/tours/ia-bacu-vas-cikavit-pitma)"
    assert _tour_urls(text, "https://teatr.org.ua/") == [
        "https://teatr.org.ua/tours/ia-bacu-vas-cikavit-pitma"
    ]


def test_markdown_city_cards_parse_ukrainian_months():
    text = """### Я бачу, вас цікавить пітьма

08 жовтня 2026, 18:00

Тернопіль, Драмтеатр

від 990 грн.

### Я, Побєда і Берлін

25 жовтня 2026, 18:00

Тернопіль, Драмтеатр

від 490 грн.
"""
    events = _markdown_city_events(text, datetime(2026, 8, 15, 8, 0))
    assert len(events) == 2
    assert events[0].title == "Я бачу, вас цікавить пітьма"
    assert events[0].start_at == datetime(2026, 10, 8, 18, 0)
    assert events[0].venue == "Драмтеатр"
    assert events[0].price_text == "від 990 грн"
    assert events[1].title == "Я, Побєда і Берлін"


def test_future_city_events_does_not_stop_after_nonmatching_parser():
    text = """### Я бачу, вас цікавить пітьма

08 жовтня 2026, 18:00

Тернопіль, Драмтеатр

від 990 грн.

### Я, Побєда і Берлін

25 жовтня 2026, 18:00

Тернопіль, Драмтеатр

від 490 грн.
"""
    events = _future_city_events(text, datetime(2026, 8, 15, 8, 0))
    assert {event.title for event in events} == {
        "Я бачу, вас цікавить пітьма",
        "Я, Побєда і Берлін",
    }
