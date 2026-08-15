from app.collectors.teatr_org_ua import _event_urls, _tour_urls


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
