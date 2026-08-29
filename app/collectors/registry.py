from app.collectors import concert_ua, internet_bilet, ixyt, kvytok, list_in_ua, moemisto, murava, numotamo, teatr_org_ua, ticket_dp, ticket_kiev, ticketsbox, ternopilcity, ua_0352
from app.collectors import karabas

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
]

OPTIONAL_COLLECTORS = [
    (ticketsbox.SOURCE_NAME, ticketsbox.BASE_URL, ticketsbox.collect),
    (ixyt.SOURCE_NAME, ixyt.BASE_URL, ixyt.collect),
    (ua_0352.SOURCE_NAME, ua_0352.BASE_URL, ua_0352.collect),
    (ternopilcity.SOURCE_NAME, ternopilcity.BASE_URL, ternopilcity.collect),
    (internet_bilet.SOURCE_NAME, internet_bilet.BASE_URL, internet_bilet.collect),
]

COLLECTORS = PRODUCTION_COLLECTORS


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

    if errors:
        raise RuntimeError("Invalid production collector registry:\n- " + "\n- ".join(errors))


validate_collectors()
