from datetime import datetime
from app.collectors.karabas import _parse_date_time

def test_parse_date():
    assert _parse_date_time("23 Нд серпня ’ 2026 17:00") == datetime(2026,8,23,17,0)
