from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class TelegramUser(Base):
    __tablename__ = "telegram_users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    timezone: Mapped[str] = mapped_column(String(64), default="Europe/Kyiv")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    __table_args__ = (UniqueConstraint("user_id", name="uq_notification_user"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True)
    daily_tomorrow: Mapped[bool] = mapped_column(Boolean, default=False)
    new_ticket_sales: Mapped[bool] = mapped_column(Boolean, default=False)
    weekend_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    send_hour: Mapped[int] = mapped_column(Integer, default=18)


class FavoriteNotification(Base):
    __tablename__ = "favorite_notifications"
    __table_args__ = (UniqueConstraint("user_id", "group_key", name="uq_favorite_notification_user_group"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("telegram_users.id"), index=True)
    group_key: Mapped[str] = mapped_column(String(64), index=True)
    notify_before_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
