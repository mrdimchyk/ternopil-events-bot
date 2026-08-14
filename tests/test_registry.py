from app.collectors.registry import COLLECTORS


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
