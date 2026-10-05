from app.collectors import ticketsfest


LIVE_FIXTURE = """
<div class="event-card">
  <a href="/en/events/wellboy/">
    <img alt="Wellboy">
    <h3>Wellboy</h3>
  </a>
  <div>18.09.2026 · 17:00</div>
  <div>Ternopil · Сoncert Hall PODOLYANY</div>
  <div>from 800 ₴ Tickets</div>
</div>
"""


def test_ticketsfest_contract_points_to_ternopil_catalog():
    assert ticketsfest.SOURCE_NAME == "TicketsFest"
    assert ticketsfest.BASE_URL == "https://ticketsfest.com.ua/en/events/ternopil/"


def test_ticketsfest_parses_live_card_structure():
    events = ticketsfest._parse_cards(LIVE_FIXTURE)
    assert len(events) == 1
    event = events[0]
    assert event.title == "Wellboy"
    assert event.venue == "Сoncert Hall PODOLYANY"
    assert event.start_at.strftime("%Y-%m-%d %H:%M") == "2026-09-18 17:00"
    assert event.price_text == "800 ₴"
    assert event.ticket_url == "https://ticketsfest.com.ua/en/events/wellboy/"


def test_city_heading_does_not_consume_first_event_or_catalog_link():
    html = '<html><body><main><h2>Concerts and events in Ternopil, Ukraine</h2>'
    html += '<a href="/en/events/ternopil/">Ternopil</a>' + LIVE_FIXTURE
    html += LIVE_FIXTURE.replace('wellboy', 'homin').replace('Wellboy', 'Гомін')
    html += '</main></body></html>'
    events = ticketsfest._parse_cards(html)
    assert [e.title for e in events] == ['Wellboy', 'Гомін']


def test_catalog_heading_with_single_event_is_never_event():
    html = '<div><h2>Concerts and events in Ternopil, Ukraine</h2>'
    html += '<a href="/en/events/ternopil/">Ternopil</a>' + LIVE_FIXTURE + '</div>'
    assert [e.title for e in ticketsfest._parse_cards(html)] == ['Wellboy']
