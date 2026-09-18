from app.collectors.registry import (
    COLLECTORS,
    OPTIONAL_COLLECTORS,
    PRODUCTION_COLLECTORS,
    source_tier,
)


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
        "iXYt.info",
        "Pulse Live",
        "20 хвилин Тернопіль",
        "Тернопільська обласна філармонія",
        "Тернопільський академічний театр ім. Т. Г. Шевченка",
        "TicketsFest",
    ]
    assert OPTIONAL_COLLECTORS


def test_low_marginal_value_or_unreliable_sources_are_secondary_not_core():
    assert source_tier("iXYt.info") == "secondary"
    assert source_tier("Kvytok") == "secondary"
    assert source_tier("Pulse Live") == "secondary"
