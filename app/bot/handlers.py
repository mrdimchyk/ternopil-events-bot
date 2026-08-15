from datetime import datetime, timedelta

from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.db.session import SessionLocal
from app.services.event_queries import CanonicalDbEvent, canonical_events_for_category, canonical_events_for_range, canonical_events_for_day, category_counts
from app.services.event_search import search_canonical_events
from app.services.favorites import add_favorite, favorite_events, favorite_group_keys, remove_favorite
from app.services.notifications import notification_group_keys, subscribe_favorite, unsubscribe_favorite

router = Router()


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 Сьогодні", callback_data="events:today"), InlineKeyboardButton(text="📅 Завтра", callback_data="events:tomorrow")],
        [InlineKeyboardButton(text="📆 Вихідні", callback_data="events:weekend"), InlineKeyboardButton(text="🎭 Категорії", callback_data="categories")],
        [InlineKeyboardButton(text="🔎 Пошук", callback_data="search"), InlineKeyboardButton(text="❤️ Обране", callback_data="favorites")],
        [InlineKeyboardButton(text="🔔 Сповіщення", callback_data="notifications")],
    ])


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


def _events_keyboard(events: list[CanonicalDbEvent], favorite_keys: set[str], notification_keys: set[str]) -> InlineKeyboardMarkup:
    rows = []
    for item in events:
        event = item.representative
        favorite_label = "💛 В обраному" if event.group_key in favorite_keys else "❤️ Додати в обране"
        notification_label = "🔕 Вимкнути нагадування" if event.group_key in notification_keys else "🔔 Нагадати за 24 год"
        rows.append([InlineKeyboardButton(text=favorite_label, callback_data=f"favorite:{event.group_key}")])
        rows.append([InlineKeyboardButton(text=notification_label, callback_data=f"notify:{event.group_key}")])
        offers = [s for s in item.sources if s.ticket_url]
        for index, source in enumerate(offers, start=1):
            label = f"🎟️ {event.title[:38]}" if len(offers) == 1 else f"🎟️ {event.title[:32]} — квитки {index}"
            rows.append([InlineKeyboardButton(text=label, url=source.ticket_url)])
    rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _send_events(message: Message, events: list[CanonicalDbEvent], heading: str) -> None:
    if not events:
        await message.answer(f"📅 <b>{heading}</b>\n\nПоки що подій у базі немає.", reply_markup=main_menu())
        return
    with SessionLocal() as session:
        favorite_keys = favorite_group_keys(session, message.from_user.id)
        notification_keys = notification_group_keys(session, message.from_user.id)
    text = f"📅 <b>{heading}</b>\n\n" + "\n\n".join(_format_event(item) for item in events[:20])
    if len(events) > 20:
        text += f"\n\n…і ще {len(events) - 20} подій."
    await message.answer(text, reply_markup=_events_keyboard(events[:20], favorite_keys, notification_keys))


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


@router.callback_query(lambda c: c.data and c.data.startswith("favorite:"))
async def toggle_favorite(callback: CallbackQuery):
    group_key = callback.data.split(":", 1)[1]
    with SessionLocal() as session:
        if group_key in favorite_group_keys(session, callback.from_user.id):
            remove_favorite(session, callback.from_user.id, group_key)
            text = "Видалено з обраного ❤️"
        else:
            add_favorite(session, callback.from_user.id, group_key)
            text = "Додано в обране 💛"
    await callback.answer(text)


@router.callback_query(lambda c: c.data and c.data.startswith("notify:"))
async def toggle_notification(callback: CallbackQuery):
    group_key = callback.data.split(":", 1)[1]
    with SessionLocal() as session:
        if group_key in notification_group_keys(session, callback.from_user.id):
            unsubscribe_favorite(session, callback.from_user.id, group_key)
            text = "Нагадування вимкнено 🔕"
        else:
            subscribe_favorite(session, callback.from_user.id, group_key)
            text = "Нагадування встановлено на 24 години до події 🔔"
    await callback.answer(text)


@router.callback_query(lambda c: c.data == "favorites")
async def favorites(callback: CallbackQuery):
    await callback.answer()
    with SessionLocal() as session:
        events = favorite_events(session, callback.from_user.id, datetime.now())
    await _send_events(callback.message, events, "Моє обране")


@router.callback_query(lambda c: c.data == "notifications")
async def notifications(callback: CallbackQuery):
    await callback.answer()
    with SessionLocal() as session:
        keys = notification_group_keys(session, callback.from_user.id)
    await callback.message.answer(f"🔔 <b>Сповіщення</b>\n\nАктивних нагадувань: {len(keys)}\n\nНагадування надсилаються за 24 години до події.", reply_markup=main_menu())


@router.callback_query(lambda c: c.data == "menu")
async def menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Оберіть, що показати:", reply_markup=main_menu())
