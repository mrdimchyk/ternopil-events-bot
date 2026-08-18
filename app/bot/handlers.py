from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from app.config import settings
from app.db.session import SessionLocal
from app.db.models import Event
from app.services.event_queries import (
    CanonicalDbEvent,
    canonical_events_for_category,
    canonical_events_for_range,
    canonical_events_for_day,
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
    rows = []
    favorite_label = "💛 В обраному" if event.group_key in favorite_keys else "❤️ Додати в обране"
    notification_label = "🔕 Вимкнути нагадування" if event.group_key in notification_keys else "🔔 Нагадати за 24 год"
    favorite_data = f"favorite_id:{event.id}"
    notification_data = f"notify_id:{event.id}"
    if len(favorite_data.encode("utf-8")) <= 64:
        rows.append([InlineKeyboardButton(text=favorite_label, callback_data=favorite_data)])
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
    """Update only the favorite/reminder labels while preserving ticket buttons."""
    message = callback.message
    if not message or not message.reply_markup:
        return

    rows: list[list[InlineKeyboardButton]] = []
    for row_index, row in enumerate(message.reply_markup.inline_keyboard):
        new_row: list[InlineKeyboardButton] = []
        for button in row:
            text = button.text
            if favorite is not None and button.callback_data and button.callback_data.startswith("favorite_id:"):
                text = "💛 В обраному" if favorite else "❤️ Додати в обране"
            elif notification is not None and button.callback_data and button.callback_data.startswith("notify_id:"):
                text = "🔕 Вимкнути нагадування" if notification else "🔔 Нагадати за 24 год"
            if text == button.text:
                new_row.append(button)
            else:
                new_row.append(button.model_copy(update={"text": text}))
        rows.append(new_row)

    await message.edit_reply_markup(reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))


async def _send_events(message: Message, events: list[CanonicalDbEvent], heading: str, user_id: int | None = None) -> None:
    """Send events with action labels based on the actual Telegram user."""
    if not events:
        await message.answer(f"📅 <b>{heading}</b>\n\nПоки що подій у базі немає.", reply_markup=main_menu())
        return

    viewer_user_id = user_id if user_id is not None else message.from_user.id
    favorite_keys: set[str] = set()
    notification_keys: set[str] = set()
    try:
        with SessionLocal() as session:
            favorite_keys = favorite_group_keys(session, viewer_user_id)
            notification_keys = notification_group_keys(session, viewer_user_id)
    except Exception:
        pass

    await message.answer(f"📅 <b>{heading}</b>")
    displayed = events[:20]
    for item in displayed:
        await message.answer(
            _format_event(item),
            reply_markup=_event_keyboard(item, favorite_keys, notification_keys),
        )
    if len(events) > 20:
        await message.answer(f"…і ще {len(events) - 20} подій.", reply_markup=main_menu())
    else:
        await message.answer("Оберіть дію або поверніться до меню:", reply_markup=main_menu())


async def _send_day(message: Message, offset: int, user_id: int | None = None) -> None:
    label = "сьогодні" if offset == 0 else "завтра"
    start, _ = _day_range(offset)
    with SessionLocal() as session:
        events = canonical_events_for_day(session, start)
    await _send_events(message, events, f"Що цікавого {label} у Тернополі", user_id=user_id)


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
        await message.answer("⚠️ Під час пошуку сталася помилка.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


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
        await _send_day(callback.message, 0 if callback.data == "events:today" else 1, user_id=callback.from_user.id)
    except Exception as exc:
        await callback.message.answer("⚠️ Не вдалося завантажити події.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


@router.callback_query(lambda c: c.data == "events:weekend")
async def weekend_events(callback: CallbackQuery):
    await callback.answer()
    try:
        start, end = _weekend_range()
        with SessionLocal() as session:
            events = canonical_events_for_range(session, start, end)
        await _send_events(callback.message, events, "Події цими вихідними у Тернополі", user_id=callback.from_user.id)
    except Exception as exc:
        await callback.message.answer("⚠️ Не вдалося завантажити вихідні.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


@router.callback_query(lambda c: c.data == "categories")
async def categories(callback: CallbackQuery):
    await callback.answer()
    try:
        start = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30)
        with SessionLocal() as session:
            counts = category_counts(session, start, end)
        rows = [[InlineKeyboardButton(text=f"🎭 {name} ({count})", callback_data=f"category:{index}")] for index, (name, count) in enumerate(counts[:12])]
        rows.append([InlineKeyboardButton(text="⬅️ Меню", callback_data="menu")])
        await callback.message.answer("Оберіть категорію на найближчі 30 днів:", reply_markup=InlineKeyboardMarkup(inline_keyboard=rows))
    except Exception as exc:
        await callback.message.answer("⚠️ Не вдалося завантажити категорії.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


@router.callback_query(lambda c: c.data and c.data.startswith("category:"))
async def category_events(callback: CallbackQuery):
    await callback.answer()
    try:
        index = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.message.answer("Не вдалося визначити категорію.", reply_markup=main_menu())
        return
    try:
        start = _local_now().replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=30)
        with SessionLocal() as session:
            counts = category_counts(session, start, end)
            if index < 0 or index >= min(len(counts), 12):
                await callback.message.answer("Категорія більше недоступна. Відкрийте категорії ще раз.", reply_markup=main_menu())
                return
            category = counts[index][0]
            events = canonical_events_for_category(session, category, start, end)
        await _send_events(callback.message, events, f"{category} — найближчі 30 днів", user_id=callback.from_user.id)
    except Exception as exc:
        await callback.message.answer("⚠️ Не вдалося завантажити події категорії.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


@router.callback_query(lambda c: c.data and c.data.startswith("favorite_id:"))
async def toggle_favorite(callback: CallbackQuery):
    try:
        event_id = int(callback.data.split(":", 1)[1])
        with SessionLocal() as session:
            group_key = _event_group_key(session, event_id)
            if not group_key:
                await callback.answer("Подію вже видалено", show_alert=True)
                return
            is_favorite = group_key in favorite_group_keys(session, callback.from_user.id)
            if is_favorite:
                remove_favorite(session, callback.from_user.id, group_key)
                text = "Видалено з обраного ❤️"
                new_state = False
            else:
                add_favorite(session, callback.from_user.id, group_key)
                text = "Додано в обране 💛"
                new_state = True
        await _refresh_event_action_buttons(callback, favorite=new_state)
        await callback.answer(text)
    except Exception as exc:
        await callback.answer(f"Помилка БД: {type(exc).__name__}", show_alert=True)


@router.callback_query(lambda c: c.data and c.data.startswith("notify_id:"))
async def toggle_notification(callback: CallbackQuery):
    try:
        event_id = int(callback.data.split(":", 1)[1])
        with SessionLocal() as session:
            group_key = _event_group_key(session, event_id)
            if not group_key:
                await callback.answer("Подію вже видалено", show_alert=True)
                return
            is_subscribed = group_key in notification_group_keys(session, callback.from_user.id)
            if is_subscribed:
                unsubscribe_favorite(session, callback.from_user.id, group_key)
                text = "Нагадування вимкнено 🔕"
                new_state = False
            else:
                subscribe_favorite(session, callback.from_user.id, group_key)
                text = "Нагадування встановлено на 24 години до події 🔔"
                new_state = True
        await _refresh_event_action_buttons(callback, notification=new_state)
        await callback.answer(text)
    except Exception as exc:
        await callback.answer(f"Помилка БД: {type(exc).__name__}", show_alert=True)


@router.callback_query(lambda c: c.data == "favorites")
async def favorites(callback: CallbackQuery):
    await callback.answer()
    try:
        with SessionLocal() as session:
            events = favorite_events(session, callback.from_user.id, _local_now())
        await _send_events(callback.message, events, "Моє обране", user_id=callback.from_user.id)
    except Exception as exc:
        await callback.message.answer("⚠️ Не вдалося завантажити обране.\n" f"Технічна причина: <code>{type(exc).__name__}: {str(exc)[:220]}</code>", reply_markup=main_menu())


@router.callback_query(lambda c: c.data == "notifications")
async def notifications(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🔔 Нагадування вмикаються кнопкою «Нагадати за 24 год» під потрібною подією.", reply_markup=main_menu())


@router.callback_query(lambda c: c.data == "menu")
async def menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.clear()
    await callback.message.answer("Головне меню:", reply_markup=main_menu())
