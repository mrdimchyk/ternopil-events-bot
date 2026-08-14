from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.models import Event
from app.db.session import SessionLocal

router = Router()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Сьогодні", callback_data="events:today"), InlineKeyboardButton(text="📅 Завтра", callback_data="events:tomorrow")],
            [InlineKeyboardButton(text="📆 Вихідні", callback_data="events:weekend"), InlineKeyboardButton(text="🎭 Категорії", callback_data="categories")],
            [InlineKeyboardButton(text="❤️ Обране", callback_data="favorites"), InlineKeyboardButton(text="🔔 Сповіщення", callback_data="notifications")],
        ]
    )


def _day_range(offset: int) -> tuple[datetime, datetime]:
    now = datetime.now()
    target = (now + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
    return target, target + timedelta(days=1)


def _format_event(event: Event) -> str:
    time = event.start_at.strftime("%H:%M") if event.start_at else "Час уточнюється"
    venue = f"📍 {event.venue.name}" if event.venue else "📍 Тернопіль"
    price = f"💰 {event.price_text}\n" if event.price_text else ""
    return f"🎟️ <b>{event.title}</b>\n🕐 {time}\n{venue}\n{price}"


def _events_for_day(offset: int) -> list[Event]:
    start, end = _day_range(offset)
    with SessionLocal() as session:
        query = (
            select(Event)
            .options(selectinload(Event.venue))
            .where(Event.start_at >= start, Event.start_at < end, Event.status == "active")
            .order_by(Event.start_at, Event.title)
        )
        return list(session.scalars(query).all())


def _events_keyboard(events: list[Event]) -> InlineKeyboardMarkup:
    rows = []
    for event in events:
        if event.ticket_url:
            rows.append([InlineKeyboardButton(text=f"🎟️ {event.title[:45]}", url=event.ticket_url)])
    rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_day(message: Message, offset: int) -> None:
    label = "сьогодні" if offset == 0 else "завтра"
    events = _events_for_day(offset)
    if not events:
        await message.answer(f"📅 <b>{label.capitalize()}</b>\n\nПоки що подій у базі немає.", reply_markup=main_menu())
        return
    text = f"📅 <b>Що цікавого {label} у Тернополі</b>\n\n"
    text += "\n\n".join(_format_event(event) for event in events[:20])
    if len(events) > 20:
        text += f"\n\n…і ще {len(events) - 20} подій."
    await message.answer(text, reply_markup=_events_keyboard(events[:20]))


@router.message(CommandStart())
async def start(message: Message):
    await message.answer("Привіт! 👋\n\nЯ допоможу знайти цікаві події в Тернополі.", reply_markup=main_menu())


@router.callback_query(lambda c: c.data in {"events:today", "events:tomorrow"})
async def day_events(callback: CallbackQuery):
    await callback.answer()
    await _send_day(callback.message, 0 if callback.data == "events:today" else 1)


@router.callback_query(lambda c: c.data == "menu")
async def menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Оберіть, що показати:", reply_markup=main_menu())


@router.callback_query(lambda c: c.data in {"categories", "favorites", "notifications", "events:weekend"})
async def not_implemented(callback: CallbackQuery):
    await callback.answer("Цю функцію додамо на наступному етапі 🚧", show_alert=True)
