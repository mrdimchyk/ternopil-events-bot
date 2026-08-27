from app.collectors import ticket_dp


def test_ticket_dp_contract_points_to_ternopil_catalog():
    assert ticket_dp.SOURCE_NAME == "Ticket.dp.ua"
    assert ticket_dp.BASE_URL == "https://ticket.dp.ua/ternopil/"
