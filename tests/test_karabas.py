from datetime import datetime
from pathlib import Path

from app.collectors.karabas import _extract_event_cards, _parse_date_time

FIXTURE = Path(__file__).parent / "fixtures" / "karabas_august_2026.txt"


def test_karabas_parses_month_heading_with_weekday_and_apostrophe():
    value = "19 Ср серпня ’ 2026 19:00"
    parsed = _parse_date_time(value)
    assert parsed == datetime(2026, 8, 19, 19, 0)


def test_karabas_parses_real_jina_markdown_date_heading():
    value = "**7** Пн _вересня ’ 2026_"
    from app.collectors.karabas import _is_date_heading

    assert _is_date_heading(value)


def test_karabas_real_august_2026_page_fixture():
    text = FIXTURE.read_text(encoding="utf-8")
    events = _extract_event_cards(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))

    assert len(events) == 7
    assert [event.title for event in events] == [
        "«Кіно для дорослих»",
        "FOOD FEST Тернопіль",
        "Chico & Qatoshi х ТІК | День Незалежності",
        "Відкриття концертного сезону. «Нація нескорених»",
        "Концерт ВІЧ-НА-ВІЧ",
        "«Сексуальне тренування». Комедійно-пізнавальний вечір",
        "Мюзикл «Панна Францішка»",
    ]
    assert events[0].start_at == datetime(2026, 8, 19, 18, 0)
    assert events[0].venue == "Тернопільський академічний обласний український драматичний театр Т. Г. Шевченка"
    assert events[0].price_text == "300 - 650 грн"
    assert events[1].start_at == datetime(2026, 8, 21, 15, 0)
    assert events[1].price_text == "700 - 1000 грн"
    assert events[2].price_text == "550 грн"
    assert events[5].start_at == datetime(2026, 8, 27, 19, 0)
    assert events[-1].start_at == datetime(2026, 8, 30, 17, 0)
    assert all(event.venue for event in events)
    assert all(event.price_text for event in events)
    assert all("Сильні серця" not in event.title for event in events)


def test_karabas_uses_specific_event_url_from_card():
    text = """19 Ср серпня ’ 2026
[«Кіно для дорослих»](https://ternopil.karabas.com/event/kino-dlya-doroslyh/)
театри
Тернопіль, 19 серпня 2026, 18:00
Тернопільський театр
300 - 650 грн
КУПИТИ
"""
    events = _extract_event_cards(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))
    assert len(events) == 1
    assert events[0].title == "«Кіно для дорослих»"
    assert events[0].ticket_url == "https://ternopil.karabas.com/event/kino-dlya-doroslyh/"
    assert events[0].source_url == events[0].ticket_url


def test_karabas_parses_jina_markdown_location_line():
    text = """**19** Ср _серпня ’ 2026_
[![Image](https://images.karabas.com/test.jpg)](https://ternopil.karabas.com/kino-dlya-doroslykh-4/)
[«Кіно для дорослих»](https://ternopil.karabas.com/kino-dlya-doroslykh-4/)
театри
**Тернопіль**, 19 серпня 2026, 18:00
Тернопільський театр
**300 - 650 грн**
[КУПИТИ](https://ternopil.karabas.com/kino-dlya-doroslykh-4/order/)
"""
    events = _extract_event_cards(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))
    assert len(events) == 1
    assert events[0].start_at == datetime(2026, 8, 19, 18, 0)
    assert events[0].ticket_url == "https://ternopil.karabas.com/kino-dlya-doroslykh-4/"
    assert events[0].price_text == "300 - 650 грн"


def test_karabas_skips_cancelled_real_card():
    text = """28 Пт серпня ’ 2026
БЕЗ ОБМЕЖЕНЬ. «Сильні серця»
концерти
Тернопіль, 28 серпня 2026, 19:00
Парковка ТРЦ Подоляни
Скасовано
"""
    events = _extract_event_cards(text, "https://ternopil.karabas.com/august/", datetime(2026, 8, 15, 0, 0))
    assert events == []
