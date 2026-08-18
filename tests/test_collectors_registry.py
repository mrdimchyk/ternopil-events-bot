from app.collectors.registry import COLLECTORS, OPTIONAL_COLLECTORS, PRODUCTION_COLLECTORS


def test_production_registry_contains_only_verified_mvp_collector():
    assert COLLECTORS == PRODUCTION_COLLECTORS
    assert [source for source, _, _ in COLLECTORS] == ["KARABAS"]
    assert OPTIONAL_COLLECTORS
