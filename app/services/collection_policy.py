# A zero-result source is treated as a collector regression unless the source
# is explicitly known to be legitimately empty. This prevents HTTP/parsing
# failures from being silently reported as successful runs.
# MURAVA's official public events block is currently empty, so zero results are
# a valid source state rather than evidence of a parser regression.
ALLOW_EMPTY_SOURCES = {"TicketsBox", "MURAVA"}


def collection_should_fail(*, core_failures: int, core_quality_errors: int) -> bool:
    """Only core-source failures or core data-quality errors invalidate useful ingest."""
    return bool(core_failures or core_quality_errors)
