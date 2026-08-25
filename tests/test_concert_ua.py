from app.collectors import concert_ua


def test_concert_ua_uses_browser_like_headers(monkeypatch):
    captured = {}

    def fake_collect_jsonld(url, source_name, timeout=20.0, headers=None):
        captured.update(
            {
                "url": url,
                "source_name": source_name,
                "timeout": timeout,
                "headers": headers,
            }
        )
        return []

    monkeypatch.setattr(concert_ua, "collect_jsonld", fake_collect_jsonld)

    assert concert_ua.collect(timeout=7.5) == []
    assert captured["url"] == concert_ua.BASE_URL
    assert captured["source_name"] == concert_ua.SOURCE_NAME
    assert captured["timeout"] == 7.5
    assert captured["headers"]["User-Agent"].startswith("Mozilla/5.0")
    assert captured["headers"]["Accept"].startswith("text/html")
    assert captured["headers"]["Referer"] == "https://concert.ua/uk/ternopil"
