from app.collectors import murava


def test_murava_contract_points_to_official_events_page():
    assert murava.SOURCE_NAME == "MURAVA"
    assert murava.BASE_URL == "https://www.murava.life/"


def test_murava_delegates_to_shared_html_collector(monkeypatch):
    expected = [object()]
    calls = {}

    def fake_collect(url, source_name=None, timeout=20.0):
        calls.update(url=url, source_name=source_name, timeout=timeout)
        return expected

    monkeypatch.setattr(murava, "collect_html", fake_collect)

    result = murava.collect(timeout=7.5)

    assert result == expected
    assert calls == {
        "url": murava.BASE_URL,
        "source_name": murava.SOURCE_NAME,
        "timeout": 7.5,
    }
