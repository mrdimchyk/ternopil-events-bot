from app.collectors import afisha_ukraine


def test_afisha_ukraine_contract(monkeypatch):
    calls = []

    def fake_collect_html(url, source_name, timeout=20.0):
        calls.append((url, source_name, timeout))
        return []

    monkeypatch.setattr(afisha_ukraine, "collect_html", fake_collect_html)

    assert afisha_ukraine.collect(timeout=7.5) == []
    assert calls == [(afisha_ukraine.BASE_URL, afisha_ukraine.SOURCE_NAME, 7.5)]
