from app.collectors import concert_ua, filarmony_te, internet_bilet, ixyt, kasa, kvytok, list_in_ua, moemisto, murava, numotamo, pulselive, teatr_org_ua, ticket_dp, ticket_kiev, ticketsbox, ternopilcity, ticketsfest, ua_0352, twentyminut, theatre_te
from app.collectors import karabas

# Source tiers are operational policy, based on production evidence rather than
# adapter existence. Core failures are release/collection blockers; secondary
# and quarantined sources remain collected and reported, but cannot invalidate
# otherwise useful ingest. Quarantined sources are known degraded sources that
# stay visible so recovery can be detected without parser guesswork.
CORE_SOURCE_NAMES = {
    karabas.SOURCE_NAME,
    numotamo.SOURCE_NAME,
    moemisto.SOURCE_NAME,
    ternopilcity.SOURCE_NAME,
    kasa.SOURCE_NAME,
    internet_bilet.SOURCE_NAME,
}

QUARANTINED_SOURCE_NAMES = {
    concert_ua.SOURCE_NAME,
    list_in_ua.SOURCE_NAME,
    twentyminut.SOURCE_NAME,
}

# Production collectors have passed source-access, parser, ingest and quality checks.
PRODUCTION_COLLECTORS = [
    (karabas.SOURCE_NAME, karabas.BASE_URL, karabas.collect),
    (numotamo.SOURCE_NAME, numotamo.BASE_URL, numotamo.collect),
    (concert_ua.SOURCE_NAME, concert_ua.BASE_URL, concert_ua.collect),
    (teatr_org_ua.SOURCE_NAME, teatr_org_ua.BASE_URL, teatr_org_ua.collect),
    (ticket_dp.SOURCE_NAME, ticket_dp.BASE_URL, ticket_dp.collect),
    (murava.SOURCE_NAME, murava.BASE_URL, murava.collect),
    (ticket_kiev.SOURCE_NAME, ticket_kiev.BASE_URL, ticket_kiev.collect),
    (list_in_ua.SOURCE_NAME, list_in_ua.BASE_URL, list_in_ua.collect),
    (moemisto.SOURCE_NAME, moemisto.BASE_URL, moemisto.collect),
    (kvytok.SOURCE_NAME, kvytok.BASE_URL, kvytok.collect),
    (ternopilcity.SOURCE_NAME, ternopilcity.BASE_URL, ternopilcity.collect),
    (kasa.SOURCE_NAME, kasa.BASE_URL, kasa.collect),
    (internet_bilet.SOURCE_NAME, internet_bilet.BASE_URL, internet_bilet.collect),
    (ixyt.SOURCE_NAME, ixyt.BASE_URL, ixyt.collect),
    (pulselive.SOURCE_NAME, pulselive.BASE_URL, pulselive.collect),
    (twentyminut.SOURCE_NAME, twentyminut.BASE_URL, twentyminut.collect),
    (filarmony_te.SOURCE_NAME, filarmony_te.BASE_URL, filarmony_te.collect),
    (theatre_te.SOURCE_NAME, theatre_te.BASE_URL, theatre_te.collect),
    (ticketsfest.SOURCE_NAME, ticketsfest.BASE_URL, ticketsfest.collect),
]

OPTIONAL_COLLECTORS = [
    (ticketsbox.SOURCE_NAME, ticketsbox.BASE_URL, ticketsbox.collect),
    (ua_0352.SOURCE_NAME, ua_0352.BASE_URL, ua_0352.collect),
]

COLLECTORS = PRODUCTION_COLLECTORS
SECONDARY_SOURCE_NAMES = {
    name for name, _, _ in COLLECTORS
    if name not in CORE_SOURCE_NAMES | QUARANTINED_SOURCE_NAMES
}


def source_tier(source_name: str) -> str:
    if source_name in CORE_SOURCE_NAMES:
        return "core"
    if source_name in QUARANTINED_SOURCE_NAMES:
        return "quarantined"
    if source_name in SECONDARY_SOURCE_NAMES:
        return "secondary"
    return "candidate"


def validate_collectors() -> None:
    """Fail fast when a production collector does not implement the registry contract."""
    errors: list[str] = []
    seen_names: set[str] = set()
    seen_urls: set[str] = set()

    for index, (source_name, base_url, collect) in enumerate(COLLECTORS, start=1):
        prefix = f"production collector #{index}"
        if not isinstance(source_name, str) or not source_name.strip():
            errors.append(f"{prefix}: SOURCE_NAME must be a non-empty string")
        elif source_name in seen_names:
            errors.append(f"{prefix}: duplicate SOURCE_NAME {source_name!r}")
        else:
            seen_names.add(source_name)

        if not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")):
            errors.append(f"{prefix}: BASE_URL must be an absolute HTTP(S) URL")
        elif base_url in seen_urls:
            errors.append(f"{prefix}: duplicate BASE_URL {base_url!r}")
        else:
            seen_urls.add(base_url)

        if not callable(collect):
            errors.append(f"{prefix} ({source_name!r}): collect must be callable")

    classified = CORE_SOURCE_NAMES | SECONDARY_SOURCE_NAMES | QUARANTINED_SOURCE_NAMES
    if classified != seen_names:
        errors.append("source tier classification must cover every production collector exactly")
    if CORE_SOURCE_NAMES & QUARANTINED_SOURCE_NAMES:
        errors.append("a source cannot be both core and quarantined")

    if errors:
        raise RuntimeError("Invalid production collector registry:\n- " + "\n- ".join(errors))


validate_collectors()
