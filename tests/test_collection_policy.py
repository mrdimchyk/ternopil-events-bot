from scripts.collect_all import ALLOW_EMPTY_SOURCES


def test_murava_empty_catalog_is_explicitly_allowed():
    assert "MURAVA" in ALLOW_EMPTY_SOURCES
    assert "TicketsBox" in ALLOW_EMPTY_SOURCES
