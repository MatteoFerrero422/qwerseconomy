from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

def start_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📝 Зарегистрироваться',callback_data='auth:register')],[InlineKeyboardButton(text='🔐 Войти',callback_data='auth:login')]])

def main_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🛒 Магазин',callback_data='menu:shop')],
        [InlineKeyboardButton(text='⭐ Донат-магазин',callback_data='menu:donate'),InlineKeyboardButton(text='💰 Скупщик',callback_data='menu:buyer')],
        [InlineKeyboardButton(text='🎁 Кейсы',callback_data='menu:cases'),InlineKeyboardButton(text='📋 Задания',callback_data='menu:quests')],
        [InlineKeyboardButton(text='👥 Пригласить друзей',callback_data='menu:referrals'),InlineKeyboardButton(text='🏆 Топ игроков',callback_data='menu:top')],
    ])
