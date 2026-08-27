from app.collectors import murava


def test_murava_contract_points_to_official_events_page():
    assert murava.SOURCE_NAME == "MURAVA"
    assert murava.BASE_URL == "https://www.murava.life/"
