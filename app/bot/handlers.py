from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
router=Router()

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📅 Сьогодні",callback_data="today"),InlineKeyboardButton(text="📅 Завтра",callback_data="tomorrow")],[InlineKeyboardButton(text="📆 Вихідні",callback_data="weekend"),InlineKeyboardButton(text="🎭 Категорії",callback_data="categories")],[InlineKeyboardButton(text="❤️ Обране",callback_data="favorites"),InlineKeyboardButton(text="🔔 Сповіщення",callback_data="notifications")]])

@router.message(CommandStart())
async def start(message: Message):
    await message.answer("Привіт! 👋\n\nЯ допоможу знайти цікаві події в Тернополі.",reply_markup=main_menu())
