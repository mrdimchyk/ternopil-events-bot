from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.session import SessionLocal
from app.services.event_queries import CanonicalDbEvent, canonical_events_for_day

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


def _format_event(item: CanonicalDbEvent) -> str:
    event = item.representative
    time = event.start_at.strftime("%H:%M") if event.start_at else "Час уточнюється"
    venue = f"📍 {event.venue.name}" if event.venue else "📍 Тернопіль"
    prices = sorted({source.price_text for source in item.sources if source.price_text})
    price = f"💰 {', '.join(prices)}\n" if prices else ""
    return f"🎟️ <b>{event.title}</b>\n🕐 {time}\n{venue}\n{price}"


def _events_for_day(offset: int) -> list[CanonicalDbEvent]:
    start, _ = _day_range(offset)
    with SessionLocal() as session:
        return canonical_events_for_day(session, start)


def _events_keyboard(events: list[CanonicalDbEvent]) -> InlineKeyboardMarkup:
    rows = []
    for item in events:
        event = item.representative
        offers = [source for source in item.sources if source.ticket_url]
        if not offers:
            continue
        for index, source in enumerate(offers, start=1):
            label = f"🎟️ {event.title[:38]}" if len(offers) == 1 else f"🎟️ {event.title[:32]} — квитки {index}"
            rows.append([InlineKeyboardButton(text=label, url=source.ticket_url)])
    rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_day(message: Message, offset: int) -> None:
    label = "сьогодні" if offset == 0 else "завтра"
    events = _events_for_day(offset)
    if not events:
        await message.answer(f"📅 <b>{label.capitalize()}</b>\n\nПоки що подій у базі немає.", reply_markup=main_menu())
        return
    text = f"📅 <b>Що цікавого {label} у Тернополі</b>\n\n"
    text += "\n\n".join(_format_event(item) for item in events[:20])
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
