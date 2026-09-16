from datetime import datetime

from app.collectors.master_show import _collect_from_html


HTML = '''
<div>
  <div>25 вересень 18:00
    <a href="/events/2026-09-25/druha-rika/ternopil">Друга Ріка. Я Є! 30 років</a>
    <div>Тернопіль, Палац культури «Березіль» імені Леся Курбаса</div>
    <div>від 390 UAH</div>
  </div>
  <div>25 вересень 18:00
    <a href="/events/2026-09-25/druha-rika/ternopil">Друга Ріка. Я Є! 30 років</a>
    <div>Тернопіль, Палац культури «Березіль» імені Леся Курбаса</div>
    <div>від 390 UAH</div>
  </div>
  <div>25 вересень 18:00
    <a href="/events/2026-09-25/druha-rika/lutsk">Друга Ріка. Я Є! 30 років</a>
    <div>Луцьк, Розважальний Центр «Промінь»</div>
    <div>від 1190 UAH</div>
  </div>
</div>
'''


def test_collects_current_ternopil_event_from_observed_listing_shape():
    events = _collect_from_html(HTML, now=datetime(2026, 9, 17, 0, 0))
    assert len(events) == 1
    event = events[0]
    assert event.title == "Друга Ріка. Я Є! 30 років"
    assert event.start_at == datetime(2026, 9, 25, 18, 0)
    assert event.venue == "Палац культури «Березіль» імені Леся Курбаса"
    assert event.price_text == "від 390 UAH"
    assert event.ticket_url.endswith("/events/2026-09-25/druha-rika/ternopil")
