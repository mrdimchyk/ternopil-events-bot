from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    base_url: Mapped[str] = mapped_column(String(500))
    events = relationship("Event", back_populates="source")
    runs = relationship("SourceRun", back_populates="source", cascade="all, delete-orphan")


class Venue(Base):
    __tablename__ = "venues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Ternopil")
    events = relationship("Event", back_populates="venue")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (UniqueConstraint("source_id", "external_id", name="uq_event_source_external"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    external_id: Mapped[str] = mapped_column(String(255))
    group_key: Mapped[str] = mapped_column(String(64), index=True)
    title: Mapped[str] = mapped_column(String(500), index=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price_text: Mapped[str | None] = mapped_column(String(255), nullable=True)
    ticket_url: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    source_url: Mapped[str] = mapped_column(String(1000))
    status: Mapped[str] = mapped_column(String(50), default="active")
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    venue_id: Mapped[int | None] = mapped_column(ForeignKey("venues.id"), nullable=True)

    source = relationship("Source", back_populates="events")
    venue = relationship("Venue", back_populates="events")
    changes = relationship("EventChange", back_populates="event", cascade="all, delete-orphan")


class Favorite(Base):
    __tablename__ = "favorites"
    __table_args__ = (UniqueConstraint("user_id", "group_key", name="uq_favorite_user_group"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    group_key: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class EventChange(Base):
    __tablename__ = "event_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("events.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(50), index=True)
    field_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    event = relationship("Event", back_populates="changes")


class SourceRun(Base):
    __tablename__ = "source_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="running", index=True)
    collected_count: Mapped[int] = mapped_column(Integer, default=0)
    changed_count: Mapped[int] = mapped_column(Integer, default=0)
    error_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    source = relationship("Source", back_populates="runs")
