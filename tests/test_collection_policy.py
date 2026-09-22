from app.services.collection_policy import ALLOW_EMPTY_SOURCES, collection_should_fail


def test_murava_empty_catalog_is_explicitly_allowed():
    assert "MURAVA" in ALLOW_EMPTY_SOURCES
    assert "TicketsBox" in ALLOW_EMPTY_SOURCES


def test_noncore_quality_error_does_not_invalidate_useful_ingest():
    assert not collection_should_fail(core_failures=0, core_quality_errors=0)


def test_core_failure_invalidates_collection():
    assert collection_should_fail(core_failures=1, core_quality_errors=0)


def test_core_quality_error_invalidates_collection():
    assert collection_should_fail(core_failures=0, core_quality_errors=1)
