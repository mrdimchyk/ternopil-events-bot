from app.collectors import concert_ua, numotamo, teatr_org_ua, ticket_kiev, ticketsbox
from app.collectors import karabas

# Production MVP deliberately runs only the verified KARABAS collector.
# Additional adapters stay registered as optional work and are not allowed to
# block the production loop until deployment/DB/Telegram/digest is proven end-to-end.
PRODUCTION_COLLECTORS = [
    (karabas.SOURCE_NAME, karabas.BASE_URL, karabas.collect),
]

OPTIONAL_COLLECTORS = [
    (numotamo.SOURCE_NAME, numotamo.BASE_URL, numotamo.collect),
    (teatr_org_ua.SOURCE_NAME, teatr_org_ua.BASE_URL, teatr_org_ua.collect),
    (ticketsbox.SOURCE_NAME, ticketsbox.BASE_URL, ticketsbox.collect),
    (ticket_kiev.SOURCE_NAME, ticket_kiev.BASE_URL, ticket_kiev.collect),
    (concert_ua.SOURCE_NAME, concert_ua.BASE_URL, concert_ua.collect),
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
