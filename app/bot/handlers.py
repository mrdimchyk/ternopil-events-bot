from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Event
from app.services.event_queries import (
    CanonicalDbEvent,
    canonical_events_for_category,
    canonical_events_for_range,
    canonical_events_for_day,
    canonicalize_db_events,
    category_counts,
)
from app.services.event_identity import title_without_embedded_datetime
from app.services.event_search import search_canonical_events
from app.services.favorites import add_favorite, favorite_events, favorite_group_keys, remove_favorite
from app.services.notifications import notification_group_keys, subscribe_favorite, unsubscribe_favorite

router = Router()


class SearchState(StatesGroup):
    waiting_for_query = State()


def _local_now() -> datetime:
    return datetime.now(ZoneInfo(settings.timezone))


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сьогодні", callback_data="events:today"), InlineKeyboardButton(text="📅 Завтра", callback_data="events:tomorrow")],
        [InlineKeyboardButton(text="📆 Вихідні", callback_data="events:weekend"), InlineKeyboardButton(text="🎭 Категорії", callback_data="categories")],
        [InlineKeyboardButton(text="🔎 Пошук", callback_data="search"), InlineKeyboardButton(text="❤️ Обране", callback_data="favorites")],
        [InlineKeyboardButton(text="🔔 Сповіщення", callback_data="notifications")],
    ])


def _day_range(offset: int) -> tuple[datetime, datetime]:
    now = _local_now()
    target = (now + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
    return target, target + timedelta(days=1)


def _display_date(start_at: datetime | None) -> str:
    if start_at is None:
        return "Дата уточнюється"
    tzinfo = getattr(start_at, "tzinfo", None)
    local = start_at if tzinfo is None else start_at.astimezone(ZoneInfo(settings.timezone))
    return local.strftime("%d.%m.%Y")


def _display_start(start_at: datetime | None) -> str:
    if start_at is None:
        return "Час уточнюється"
    tzinfo = getattr(start_at, "tzinfo", None)
    local = start_at if tzinfo is None else start_at.astimezone(ZoneInfo(settings.timezone))
    return local.strftime("%H:%M")


def _format_event(item: CanonicalDbEvent) -> str:
    event = item.representative
    title = title_without_embedded_datetime(event.title)
    date = _display_date(event.start_at)
    time = _display_start(event.start_at)
    venue = f"📍 {event.venue.name}" if event.venue else "📍 Тернопіль"
    prices = sorted({source.price_text for source in item.sources if source.price_text})
    price = f"💰 {', '.join(prices)}\n" if prices else ""
    return f"🎟️ <b>{title}</b>\n📅 {date}\n🕐 {time}\n{venue}\n{price}"


def _event_keyboard(item: CanonicalDbEvent, favorite_keys: set[str], notification_keys: set[str]) -> InlineKeyboardMarkup:
    event = item.representative
    source_keys = {source.group_key for source in item.sources}
    favorite_label = "💛 В обраному" if source_keys & favorite_keys else "❤️ Додати в обране"
    notification_label = "🔕 Вимкнути нагадування" if source_keys & notification_keys else "🔔 Нагадати за 24 год"
    favorite_data = f"favorite_id:{event.id}"
    notification_data = f"notify_id:{event.id}"
    if len(favorite_data.encode("utf-8")) <= 64:
        rows = [[InlineKeyboardButton(text=favorite_label, callback_data=favorite_data)]]
    else:
        rows = []
    if len(notification_data.encode("utf-8")) <= 64:
        rows.append([InlineKeyboardButton(text=notification_label, callback_data=notification_data)])

    offers = [s for s in item.sources if s.ticket_url]
    for index, source in enumerate(offers, start=1):
        clean_title = title_without_embedded_datetime(event.title)
        label = f"🎟️ {clean_title[:38]}" if len(offers) == 1 else f"🎟️ {clean_title[:32]} — квитки {index}"
        rows.append([InlineKeyboardButton(text=label, url=source.ticket_url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _event_group_key(session, event_id: int) -> str | None:
    event = session.get(Event, event_id)
    return event.group_key if event else None


async def _refresh_event_action_buttons(callback: CallbackQuery, *, favorite: bool | None = None, notification: bool | None = None) -> None:
    message = callback.message
    if not message or not message.reply_markup:
        return

    rows: list[list[InlineKeyboardButton]] = []
    for row in message.reply_markup.inline_keyboard:
        new_row: list[InlineKeyboardButton] = []
        for button in row:
            text = button.text
            if favorite is not None and button.callback_data and button.callback_data.startswith("favorite_id:"):
                text = "💛 В обраному" if favorite else "❤️ Додати в обране"
            elif notification is not None and button.callback_data and button.callback_data.startswith("notify_id:"):
                text = "🔕 Вимкнути нагадування" if notification else "🔔 Нагадати за 24 год"
            new_row.append(button if text == button.text else button.model_copy(update={"text": text}))
        rows.append(new_row)

    await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


def _send_events(message: Message, events: list[CanonicalDbEvent], heading: str, user_id: int | None = None) -> None:
    pass
