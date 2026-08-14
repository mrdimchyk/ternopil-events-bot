from datetime import datetime

from app.services.event_identity import make_group_key


def test_same_event_from_two_sources_gets_same_group_key():
    start = datetime(2026, 9, 20, 19, 0)
    assert make_group_key("Concert Test", start, "Na Пошті") == make_group_key(
        "concert test", start, "Na Пошті"
    )
