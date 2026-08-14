from aiogram import Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.user_models import NotificationPreference, TelegramUser
from app.services.users import ensure_user, set_tomorrow_notifications

router = Router()


def notifications_menu(enabled: bool) -> InlineKeyboardMarkup:
    label = "🔕 Вимкнути «Завтра»" if enabled else "🔔 Увімкнути «Завтра»"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=label, callback_data="notify:tomorrow:toggle")],
        [InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")],
    ])


@router.callback_query(lambda c: c.data == "notifications")
async def notifications(callback: CallbackQuery):
    with SessionLocal() as session:
        user = ensure_user(session, callback.from_user.id, callback.from_user.first_name)
        pref = session.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
        enabled = bool(pref and pref.daily_tomorrow)
    await callback.answer()
    await callback.message.answer(
        "🔔 <b>Сповіщення</b>\n\n"
        "Поки доступне перше сповіщення: щоденний дайджест «Що цікавого завтра».\n\n"
        f"Статус: {'увімкнено' if enabled else 'вимкнено'}.",
        reply_markup=notifications_menu(enabled),
    )


@router.callback_query(lambda c: c.data == "notify:tomorrow:toggle")
async def toggle_tomorrow(callback: CallbackQuery):
    with SessionLocal() as session:
        user = ensure_user(session, callback.from_user.id, callback.from_user.first_name)
        pref = session.scalar(select(NotificationPreference).where(NotificationPreference.user_id == user.id))
        new_value = not bool(pref and pref.daily_tomorrow)
        set_tomorrow_notifications(session, callback.from_user.id, new_value)
    await callback.answer("Увімкнено" if new_value else "Вимкнено")
    await callback.message.answer(
        f"🔔 Щоденний дайджест «Що цікавого завтра» {'увімкнено' if new_value else 'вимкнено'}.",
        reply_markup=notifications_menu(new_value),
    )
