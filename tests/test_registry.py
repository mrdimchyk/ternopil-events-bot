from app.collectors.registry import COLLECTORS, validate_collectors


def test_registry_has_six_sources():
    names = [name for name, _, _ in COLLECTORS]
    assert names == [
        "KARABAS",
        "Numotamo",
        "Teatr.org.ua",
        "TicketsBox",
        "Ticket.kiev.ua",
        "Concert.ua",
    ]


def test_registry_collectors_are_callable():
    assert all(callable(collector) for _, _, collector in COLLECTORS)


def test_registry_contract_is_valid():
    validate_collectors()
