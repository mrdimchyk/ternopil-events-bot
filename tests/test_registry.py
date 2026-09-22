from app.collectors.registry import (
    COLLECTORS,
    CORE_SOURCE_NAMES,
    OPTIONAL_COLLECTORS,
    PRODUCTION_COLLECTORS,
    QUARANTINED_SOURCE_NAMES,
    SECONDARY_SOURCE_NAMES,
    source_tier,
    validate_collectors,
)
from app.services.collection_policy import collection_should_fail


def test_production_registry_contains_verified_collectors():
    assert COLLECTORS == PRODUCTION_COLLECTORS
    assert [name for name, _, _ in COLLECTORS] == ["KARABAS", "Numotamo", "Concert.ua", "Teatr.org.ua", "Ticket.dp.ua", "MURAVA", "Ticket.kiev.ua", "List.in.ua", "moemisto.ua", "Kvytok", "Ternopil City Council", "KASA.com.ua", "Internet-bilet.ua", "iXYt.info", "Pulse Live", "20 хвилин Тернопіль", "Тернопільська обласна філармонія", "Тернопільський академічний театр ім. Т. Г. Шевченка", "TicketsFest"]


def test_source_tiers_cover_production_registry_without_overlap():
    names = {name for name, _, _ in COLLECTORS}
    assert CORE_SOURCE_NAMES | SECONDARY_SOURCE_NAMES | QUARANTINED_SOURCE_NAMES == names
    assert not CORE_SOURCE_NAMES & SECONDARY_SOURCE_NAMES
    assert not CORE_SOURCE_NAMES & QUARANTINED_SOURCE_NAMES
    assert not SECONDARY_SOURCE_NAMES & QUARANTINED_SOURCE_NAMES
    assert source_tier("KARABAS") == "core"
    assert source_tier("Concert.ua") == "quarantined"
    assert source_tier("TicketsFest") == "secondary"
    assert source_tier("unknown") == "candidate"


def test_non_core_failures_do_not_invalidate_useful_ingest():
    assert not collection_should_fail(core_failures=0, core_quality_errors=0)
    assert collection_should_fail(core_failures=1, quality_errors=0)
    assert collection_should_fail(core_failures=0, quality_errors=1)


def test_optional_registry_keeps_unverified_adapters_out_of_production():
    assert OPTIONAL_COLLECTORS
    assert not {name for name, _, _ in OPTIONAL_COLLECTORS} & {name for name, _, _ in COLLECTORS}


def test_registry_collectors_are_callable():
    assert all(callable(collector) for _, _, collector in [*COLLECTORS, *OPTIONAL_COLLECTORS])


def test_registry_contract_is_valid():
    validate_collectors()
