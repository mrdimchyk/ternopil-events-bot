from app.collectors import ticket_dp


def test_ticket_dp_contract(monkeypatch):
    calls = {}

    def fake_collect_html(url, source_name, timeout=20.0):
        calls.update(url=url, source_name=source_name, timeout=timeout)
        return ["fixture-event"]

    monkeypatch.setattr(ticket_dp, "collect_html", fake_collect_html)

    result = ticket_dp.collect(timeout=7.5)

    assert result == ["fixture-event"]
    assert calls == {
        "url": "https://ticket.dp.ua/ternopil/",
        "source_name": "Ticket.dp.ua",
        "timeout": 7.5,
    }
