from types import SimpleNamespace

from app.collectors import generic_html


class _Response:
    def __init__(self, text: str):
        self.text = text

    def raise_for_status(self):
        return None


def test_afisha_ukraine_event_card_structure(monkeypatch):
    html = """
    <article class="event-card">
      <a href="/event/sexual-training">
        <h3>«Сексуальне тренування». Комедійно-пізнавальний вечір</h3>
      </a>
      <div>27-08-2026 19:00</div>
      <div>г. Тернополь</div>
      <div>БункерМуз</div>
    </article>
    """

    monkeypatch.setattr(generic_html.httpx, "get", lambda *args, **kwargs: _Response(html))

    events = generic_html.collect_html(
        "https://afisha-ukraine.com/?city=14", "Afisha-Ukraine"
    )

    assert len(events) == 1
    assert events[0].title == "«Сексуальне тренування». Комедійно-пізнавальний вечір"
    assert events[0].start_at.isoformat() == "2026-08-27T19:00:00"
    assert events[0].ticket_url == "https://afisha-ukraine.com/event/sexual-training"
