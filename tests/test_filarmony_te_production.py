from datetime import datetime
from pathlib import Path

from app.collectors import filarmony_te


FIXTURE = Path(__file__).parent / "fixtures" / "filarmony_te_homepage.html"


def test_filarmony_parses_observed_homepage_structure():
    html = FIXTURE.read_text(encoding="utf-8")
    events = filarmony_te._parse_cards(html, datetime(2026, 9, 15, 12, 0))

    assert len(events) == 2
    assert [event.title for event in events] == ["«АNІМЕ MUSIC»", "«Сойчине крило»"]
    assert [event.start_at for event in events] == [
        datetime(2026, 9, 27, 17, 0),
        datetime(2026, 9, 20, 17, 0),
    ]
    assert all(event.source_url == filarmony_te.BASE_URL for event in events)
    assert all(event.venue == filarmony_te.SOURCE_NAME for event in events)
