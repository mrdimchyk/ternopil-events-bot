from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.services.events import _event_datetime_utc


def test_naive_collector_time_is_interpreted_as_kyiv_and_stored_as_utc():
    value = _event_datetime_utc(datetime(2026, 8, 19, 21, 0))

    assert value == datetime(2026, 8, 19, 18, 0, tzinfo=timezone.utc)


def test_aware_event_time_is_converted_to_utc():
    value = _event_datetime_utc(
        datetime(2026, 8, 19, 21, 0, tzinfo=ZoneInfo("Europe/Kyiv"))
    )

    assert value == datetime(2026, 8, 19, 18, 0, tzinfo=timezone.utc)
