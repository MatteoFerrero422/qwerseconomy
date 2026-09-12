from aiogram.types import InlineKeyboardButton,InlineKeyboardMarkup
def cases_keyboard(money_cases=0,star_cases=0):
 return InlineKeyboardMarkup(inline_keyboard=[
  [InlineKeyboardButton(text=f'💵 Кейс с $ ({money_cases})',callback_data='case:money')],
  [InlineKeyboardButton(text=f'⭐ Кейс со звёздами ({star_cases})',callback_data='case:stars')],
  [InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')]])
