from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings
from app.db.session import SessionLocal
from app.services.event_queries import (
    CanonicalDbEvent,
    canonical_events_for_category,
    canonical_events_for_range,
    canonical_events_for_day,
    category_counts,
)
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


def _display_start(start_at: datetime | None) -> str:
    if start_at is None:
        return "Час уточнюється"
    tzinfo = getattr(start_at, "tzinfo", None)
    local = start_at if tzinfo is None else start_at.astimezone(ZoneInfo(settings.timezone))
    return local.strftime("%H:%M")


def _format_event(item: CanonicalDbEvent) -> str:
    event = item.representative
    time = _display_start(event.start_at)
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
    # Favorites/notifications are optional presentation data. They must never
    # prevent the actual event list from being shown when their tables fail.
    favorite_keys: set[str] = set()
    notification_keys: set[str] = set()
    try:
        with SessionLocal() as session:
            favorite_keys = favorite_group_keys(session, message.from_user.id)
            notification_keys = notification_group_keys(session, message.from_user.id)
    except Exception:
        pass
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
    today = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    days_to_saturday = (5 - today.weekday()) % 7
    saturday = today + timedelta(days=days_to_saturday)
    return saturday, saturday + timedelta(days=2)


async def _run_search(message: Message, query: str) -> None:
    query = " ".join(query.split()).strip()
    if not query:
        await message.answer("🔎 Напишіть назву або слово для пошуку, наприклад: <b>театр</b> або <b>Гомін</b>")
        return
    start = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        with SessionLocal() as session:
            events = search_canonical_events(session, query, start=start)
        await _send_events(message, events, f"Результати пошуку: «{query}»")
    except Exception as exc:
        await message.answer(
            "⚠️ Під час пошуку сталася помилка.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Привіт! 👋\n\nЯ допоможу знайти цікаві події в Тернополі.", reply_markup=main_menu())


@router.message(Command("search"))
async def search(message: Message, state: FSMContext):
    query = (message.text or "").partition(" ")[2].strip()
    await state.clear()
    if not query:
        await state.set_state(SearchState.waiting_for_query)
        await message.answer("🔎 Напишіть назву або слово для пошуку. Наприклад: <b>театр</b> або <b>Гомін</b>.")
        return
    await _run_search(message, query)


@router.callback_query(lambda c: c.data == "search")
async def search_help(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(SearchState.waiting_for_query)
    await callback.message.answer("🔎 Напишіть назву або слово для пошуку. Наприклад: <b>театр</b> або <b>Гомін</b>.")


@router.message(SearchState.waiting_for_query, F.text)
async def search_text(message: Message, state: FSMContext):
    await state.clear()
    await _run_search(message, message.text or "")


@router.callback_query(lambda c: c.data in {"events:today", "events:tomorrow"})
async def day_events(callback: CallbackQuery):
    await callback.answer()
    try:
        await _send_day(callback.message, 0 if callback.data == "events:today" else 1)
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити події.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.callback_query(lambda c: c.data == "events:weekend")
async def weekend_events(callback: CallbackQuery):
    await callback.answer()
    try:
        start, end = _weekend_range()
        with SessionLocal() as session:
            events = canonical_events_for_range(session, start, end)
        await _send_events(callback.message, events, "Події цими вихідними у Тернополі")
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити вихідні.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.callback_query(lambda c: c.data == "categories")
async def categories(callback: CallbackQuery):
    await callback.answer()
    try:
        start = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30)
        with SessionLocal() as session:
            counts = category_counts(session, start, end)
        rows = [[InlineKeyboardButton(text=f"🎭 {name} ({count})", callback_data=f"category:{index}")] for index, (name, count) in enumerate(counts[:12])]
        if counts:
            _category_cache.clear()
            _category_cache.update({index: name for index, (name, _) in enumerate(counts[:12])})
        rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
        await callback.message.answer("Оберіть категорію на найближчі 30 днів:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити категорії.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


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
    try:
        start = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30)
        with SessionLocal() as session:
            events = canonical_events_for_category(session, category, start, end)
        await _send_events(callback.message, events, f"{category} — найближчі 30 днів")
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити події категорії.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.callback_query(lambda c: c.data and c.data.startswith("favorite:"))
async def toggle_favorite(callback: CallbackQuery):
    group_key = callback.data.split(":", 1)[1]
    try:
        with SessionLocal() as session:
            if group_key in favorite_group_keys(session, callback.from_user.id):
                remove_favorite(session, callback.from_user.id, group_key)
                text = "Видалено з обраного ❤️"
            else:
                add_favorite(session, callback.from_user.id, group_key)
                text = "Додано в обране 💛"
        await callback.answer(text)
    except Exception as exc:
        await callback.answer(f"Помилка БД: {type(exc).__name__}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("notify:"))
async def toggle_notification(callback: CallbackQuery):
    group_key = callback.data.split(":", 1)[1]
    try:
        with SessionLocal() as session:
            if group_key in notification_group_keys(session, callback.from_user.id):
                unsubscribe_favorite(session, callback.from_user.id, group_key)
                text = "Нагадування вимкнено 🔕"
            else:
                subscribe_favorite(session, callback.from_user.id, group_key)
                text = "Нагадування встановлено на 24 години до події 🔔"
        await callback.answer(text)
    except Exception as exc:
        await callback.answer(f"Помилка БД: {type(exc).__name__}", show_alert=True)


@router.callback_query(lambda c: c.data == "favorites")
async def favorites(callback: CallbackQuery):
    await callback.answer()
    try:
        with SessionLocal() as session:
            events = favorite_events(session, callback.from_user.id, _local_now())
        await _send_events(callback.message, events, "Моє обране")
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити обране.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.callback_query(lambda c: c.data == "notifications")
async def notifications(callback: CallbackQuery):
    await callback.answer()
    try:
        with SessionLocal() as session:
            keys = notification_group_keys(session, callback.from_user.id)
        await callback.message.answer(f"🔔 <b>Сповіщення</b>\n\nАктивних нагадувань: {len(keys)}\n\nНагадування надсилаються за 24 години до події.", reply_markup=main_menu())
    except Exception as exc:
        await callback.message.answer(
            "⚠️ Не вдалося завантажити сповіщення.\n"
            f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>",
            reply_markup=main_menu(),
        )


@router.callback_query(lambda c: c.data == "menu")
async def menu(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("Оберіть, що показати:", reply_markup=main_menu())
