from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
def quests_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')]])
