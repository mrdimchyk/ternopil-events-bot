from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.session import SessionLocal
from app.services.event_queries import (
    CanonicalDbEvent,
    canonical_events_for_category,
    canonical_events_for_range,
    canonical_events_for_day,
    category_counts,
)
from app.services.event_search import search_canonical_events

router = Router()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Сьогодні", callback_data="events:today"), InlineKeyboardButton(text="📅 Завтра", callback_data="events:tomorrow")],
            [InlineKeyboardButton(text="📆 Вихідні", callback_data="events:weekend"), InlineKeyboardButton(text="🎭 Категорії", callback_data="categories")],
            [InlineKeyboardButton(text="🔎 Пошук", callback_data="search"), InlineKeyboardButton(text="❤️ Обране", callback_data="favorites")],
            [InlineKeyboardButton(text="🔔 Сповіщення", callback_data="notifications")],
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


async def _send_events(message: Message, events: list[CanonicalDbEvent], heading: str) -> None:
    if not events:
        await message.answer(f"📅 <b>{heading}</b>\n\nПоки що подій у базі немає.", reply_markup=main_menu())
        return
    text = f"📅 <b>{heading}</b>\n\n"
    text += "\n\n".join(_format_event(item) for item in events[:20])
    if len(events) > 20:
        text += f"\n\n…і ще {len(events) - 20} подій."
    await message.answer(text, reply_markup=_events_keyboard(events[:20]))


async def _send_day(message: Message, offset: int) -> None:
    label = "сьогодні" if offset == 0 else "завтра"
    start, _ = _day_range(offset)
    with SessionLocal() as session:
        events = canonical_events_for_day(session, start)
    await _send_events(message, events, f"Що цікавого {label} у Тернополі")


def _weekend_range() -> tuple[datetime, datetime]:
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_to_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_to_saturday)
    return saturday, saturday + timedelta(days=2)


@router.message(CommandStart())
async def start(message: Message):
    await message.answer("Привіт! 👋\n\nЯ допоможу знайти цікаві події в Тернополі.", reply_markup=main_menu())


@router.message(Command("search"))
async def search(message: Message):
    query = (message.text or "").partition(" ")[2].strip()
    if not query:
        await message.answer("🔎 Напишіть запит після команди, наприклад:\n/search театр\n/search Гомін")
        return
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    with SessionLocal() as session:
        events = search_canonical_events(session, query, start=start)
    await _send_events(message, events, f"Результати пошуку: «{query}»")


@router.callback_query(lambda c: c.data == "search")
async def search_help(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔎 Для пошуку напишіть команду, наприклад:\n/search театр\n/search Гомін")


@router.callback_query(lambda c: c.data in {"events:today", "events:tomorrow"})
async def day_events(callback: CallbackQuery):
    await callback.answer()
    await _send_day(callback.message, 0 if callback.data == "events:today" else 1)


@router.callback_query(lambda c: c.data == "events:weekend")
async def weekend_events(callback: CallbackQuery):
    await callback.answer()
    start, end = _weekend_range()
    with SessionLocal() as session:
        events = canonical_events_for_range(session, start, end)
    await _send_events(callback.message, events, "Події цими вихідними у Тернополі")


@router.callback_query(lambda c: c.data == "categories")
async def categories(callback: CallbackQuery):
    await callback.answer()
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=30)
    with SessionLocal() as session:
        counts = category_counts(session, start, end)
    rows = [[InlineKeyboardButton(text=f"🎭 {name} ({count})", callback_data=f"category:{index}")] for index, (name, count) in enumerate(counts[:12])]
    if counts:
        _category_cache.clear()
        _category_cache.update({index: name for index, (name, _) in enumerate(counts[:12])})
    rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
    await callback.message.answer("Оберіть категорію на найближчі 30 днів:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


_category_cache: dict[int, str] = {}


@router.callback_query(lambda c: c.data and c.data.startswith("category:"))
async def category_events(callback: CallbackQuery):
    await callback.answer()
    try:
        index = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.message.answer("Не вдалося визначити категорію.", reply_markup=main_menu())
        return
    category = _category_cache.get(index)
    if not category:
        await callback.message.answer("Категорії оновилися. Відкрийте їх ще раз.", reply_markup=main_menu())
        return
    start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=30)
    with SessionLocal() as session:
        events = canonical_events_for_category(session, category, start, end)
    await _send_events(callback.message, events, f"{category} — найближчі 30 днів")


@router.callback_query(lambda c: c.data == "menu")
async def menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Оберіть, що показати:", reply_markup=main_menu())


@router.callback_query(lambda c: c.data in {"favorites", "notifications"})
async def not_implemented(callback: CallbackQuery):
    await callback.answer("Цю функцію додамо на наступному етапі 🚧", show_alert=True)
