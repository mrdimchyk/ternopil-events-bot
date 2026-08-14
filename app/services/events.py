from datetime import datetime, timezone
from sqlalchemy import select
from app.db.models import Event, Source, Venue

def upsert_events(session, raw_events, source_name, base_url):
    source=session.scalar(select(Source).where(Source.name==source_name))
    if not source:
        source=Source(name=source_name,base_url=base_url); session.add(source); session.flush()
    count=0; now=datetime.now(timezone.utc).replace(tzinfo=None)
    for raw in raw_events:
        event=session.scalar(select(Event).where(Event.source_id==source.id,Event.external_id==raw.external_id))
        venue=None
        if raw.venue:
            venue=session.scalar(select(Venue).where(Venue.name==raw.venue))
            if not venue: venue=Venue(name=raw.venue,address=raw.address); session.add(venue); session.flush()
        if event is None:
            session.add(Event(external_id=raw.external_id,source_id=source.id,title=raw.title,category=raw.category,start_at=raw.start_at,venue_id=venue.id if venue else None,price_text=raw.price_text,ticket_url=raw.ticket_url,source_url=raw.source_url,description=raw.description,first_seen_at=now,last_seen_at=now)); count+=1
        else:
            event.title=raw.title; event.category=raw.category; event.start_at=raw.start_at; event.price_text=raw.price_text; event.ticket_url=raw.ticket_url; event.source_url=raw.source_url; event.last_seen_at=now
            if venue: event.venue_id=venue.id
    session.commit(); return count
