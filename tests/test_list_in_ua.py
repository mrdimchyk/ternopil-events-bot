from app.collectors import list_in_ua


def test_list_in_ua_contract_points_to_upcoming_ternopil_catalog():
    assert list_in_ua.SOURCE_NAME == "List.in.ua"
    assert "/Тернопіль/afisha/soon" in list_in_ua.BASE_URL


def test_list_in_ua_delegates_to_shared_html_collector(monkeypatch):
    expected = [object()]
    calls = {}

    def fake_collect(url, source_name=None, timeout=20.0):
        calls.update(url=url, source_name=source_name, timeout=timeout)
        return expected

    monkeypatch.setattr(list_in_ua, "collect_html", fake_collect)

    result = list_in_ua.collect(timeout=7.5)

    assert result == expected
    assert calls == {
        "url": list_in_ua.BASE_URL,
        "source_name": list_in_ua.SOURCE_NAME,
        "timeout": 7.5,
    }
