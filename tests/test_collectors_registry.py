from app.collectors.registry import COLLECTORS, OPTIONAL_COLLECTORS, PRODUCTION_COLLECTORS


def test_production_registry_contains_verified_collectors():
    assert COLLECTORS == PRODUCTION_COLLECTORS
    assert [source for source, _, _ in COLLECTORS] == ["KARABAS", "Numotamo"]
    assert OPTIONAL_COLLECTORS
