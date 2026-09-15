from app.collectors.registry import COLLECTORS, OPTIONAL_COLLECTORS, PRODUCTION_COLLECTORS, validate_collectors


def test_production_registry_contains_verified_collectors():
    assert COLLECTORS == PRODUCTION_COLLECTORS
    assert [name for name, _, _ in COLLECTORS] == ["KARABAS", "Numotamo", "Concert.ua", "Teatr.org.ua", "Ticket.dp.ua", "MURAVA", "Ticket.kiev.ua", "List.in.ua", "moemisto.ua", "Kvytok", "Ternopil City Council", "KASA.com.ua", "Internet-bilet.ua", "iXYt.info", "Pulse Live", "20 хвилин Тернопіль"]


def test_optional_registry_keeps_unverified_adapters_out_of_production():
    assert OPTIONAL_COLLECTORS
    assert not {name for name, _, _ in OPTIONAL_COLLECTORS} & {
        name for name, _, _ in COLLECTORS
    }


def test_registry_collectors_are_callable():
    assert all(callable(collector) for _, _, collector in [*COLLECTORS, *OPTIONAL_COLLECTORS])


def test_registry_contract_is_valid():
    validate_collectors()
