from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.bot.handlers import _event_keyboard, _send_events


def _item(group_key="g1"):
    event = SimpleNamespace(
        id=42,
        group_key=group_key,
        title="Jamala",
        start_at=None,
        venue=None,
    )
    source = SimpleNamespace(price_text=None, ticket_url=None)
    return SimpleNamespace(representative=event, sources=[source])


def test_event_keyboard_marks_existing_favorite_yellow():
    markup = _event_keyboard(_item("g1"), {"g1"}, set())

    assert markup.inline_keyboard[0][0].text == "💛 В обраному"


def test_event_keyboard_marks_non_favorite_red():
    markup = _event_keyboard(_item("g1"), set(), set())

    assert markup.inline_keyboard[0][0].text == "❤️ Додати в обране"


@pytest.mark.asyncio
async def test_callback_generated_event_list_uses_real_user_id_for_favorites():
    class FakeSessionContext:
        def __enter__(self):
            return object()

        def __exit__(self, *args):
            return False

    class FakeMessage:
        from_user = SimpleNamespace(id=999999)  # Telegram bot id, not the user who clicked.

        def __init__(self):
            self.markups = []

        async def answer(self, text, reply_markup=None):
            self.markups.append(reply_markup)

    message = FakeMessage()

    with (
        patch("app.bot.handlers.SessionLocal", return_value=FakeSessionContext()),
        patch("app.bot.handlers.favorite_group_keys", side_effect=lambda session, user_id: {"g1"} if user_id == 12345 else set()),
        patch("app.bot.handlers.notification_group_keys", return_value=set()),
    ):
        await _send_events(message, [_item("g1")], "Моє обране", user_id=12345)

    event_markup = message.markups[1]
    assert event_markup.inline_keyboard[0][0].text == "💛 В обраному"
