from app.collectors.teatr_org_ua import _event_urls


def test_event_urls_from_jina_markdown():
    text = "[Я бачу, вас цікавить пітьма](https://teatr.org.ua/events/ia-bacu-vas-cikavit-pitma-08-10-2026-18-00)"
    assert _event_urls(text, "https://teatr.org.ua/cities/ternopil") == [
        "https://teatr.org.ua/events/ia-bacu-vas-cikavit-pitma-08-10-2026-18-00"
    ]
