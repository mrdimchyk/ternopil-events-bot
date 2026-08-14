from sqlalchemy import select

from app.db.user_models import NotificationPreference, TelegramUser


def ensure_user(session, telegram_id: int, first_name: str | None = None) -> TelegramUser:
    user = session.scalar(select(TelegramUser).where(TelegramUser.telegram_id == telegram_id))
    if user is None:
        user = TelegramUser(telegram_id=telegram_id, first_name=first_name)
        session.add(user)
        session.flush()
        session.add(NotificationPreference(user_id=user.id))
        session.commit()
        return user

    if first_name and user.first_name != first_name:
        user.first_name = first_name
        session.commit()
    return user


def set_tomorrow_notifications(session, telegram_id: int, enabled: bool) -> None:
    user = ensure_user(session, telegram_id)
    pref = session.scalar(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    pref.daily_tomorrow = enabled
    session.commit()
