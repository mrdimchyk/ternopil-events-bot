from datetime import datetime
from app.collectors.karabas import _external_id

def test_external_id_is_stable():
    a=_external_id("https://example.com/e","Test",datetime(2026,8,20,19,0))
    b=_external_id("https://example.com/e","Test",datetime(2026,8,20,19,0))
    assert a==b
    assert len(a)==32
