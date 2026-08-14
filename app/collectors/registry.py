from app.collectors import concert_ua, numotamo, teatr_org_ua, ticket_kiev, ticketsbox
from app.collectors import karabas

COLLECTORS = [
    ("KARABAS", karabas.BASE_URL, karabas.collect),
    (numotamo.SOURCE_NAME, numotamo.BASE_URL, numotamo.collect),
    (teatr_org_ua.SOURCE_NAME, teatr_org_ua.BASE_URL, teatr_org_ua.collect),
    (ticketsbox.SOURCE_NAME, ticketsbox.BASE_URL, ticketsbox.collect),
    (ticket_kiev.SOURCE_NAME, ticket_kiev.BASE_URL, ticket_kiev.collect),
    (concert_ua.SOURCE_NAME, concert_ua.BASE_URL, concert_ua.collect),
]
