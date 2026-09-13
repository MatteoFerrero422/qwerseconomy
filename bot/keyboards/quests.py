from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CHANNEL_URL = 'https://t.me/Pepexspace'


def quests_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='📢 Наш канал', url=CHANNEL_URL)],
        [InlineKeyboardButton(text='🔎 Проверить подписку', callback_data='quest:check_sub')],
        [InlineKeyboardButton(text='◀️ Назад', callback_data='back:main')],
    ])
