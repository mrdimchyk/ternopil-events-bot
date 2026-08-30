from app.collectors.registry import COLLECTORS, OPTIONAL_COLLECTORS, PRODUCTION_COLLECTORS


def test_production_registry_contains_verified_collectors():
    assert COLLECTORS == PRODUCTION_COLLECTORS
    assert [source for source, _, _ in COLLECTORS] == [
        "KARABAS",
        "Numotamo",
        "Concert.ua",
        "Teatr.org.ua",
        "Ticket.dp.ua",
        "MURAVA",
        "Ticket.kiev.ua",
        "List.in.ua",
        "moemisto.ua",
        "Kvytok",
        "Ternopil City Council",
        "KASA.com.ua",
        "Internet-bilet.ua",
    ]
    assert OPTIONAL_COLLECTORS
