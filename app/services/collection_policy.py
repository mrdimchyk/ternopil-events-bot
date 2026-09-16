# A zero-result source is treated as a collector regression unless the source
# is explicitly known to be legitimately empty. This prevents HTTP/parsing
# failures from being silently reported as successful runs.
# MURAVA's official public events block is currently empty, so zero results are
# a valid source state rather than evidence of a parser regression.
ALLOW_EMPTY_SOURCES = {"TicketsBox", "MURAVA"}
