from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.resources import RESOURCES
from services.businesses import BUSINESSES

def shop_menu_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='📦 Покупка ресурсов',callback_data='shop:resources')],[InlineKeyboardButton(text='🏪 Бизнесы',callback_data='shop:businesses')],[InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')]])
def resource_list_keyboard(prefix,back):
    rows=[[InlineKeyboardButton(text=f"{i['emoji']} {i['name']} — {i['buy_price']}$",callback_data=f'{prefix}:{k}')] for k,i in RESOURCES.items()]; rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data=back)]); return InlineKeyboardMarkup(inline_keyboard=rows)
def business_list_keyboard():
    rows=[[InlineKeyboardButton(text=f"{i['emoji']} {i['name']}",callback_data=f'business_view:{k}')] for k,i in BUSINESSES.items()]; rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data='menu:shop')]); return InlineKeyboardMarkup(inline_keyboard=rows)
def business_confirm_keyboard(t): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Купить',callback_data=f'business_confirm:{t}')],[InlineKeyboardButton(text='❌ Отмена',callback_data='shop:businesses')]])
def business_instances_keyboard(instances,back='shop:businesses'):
    rows=[[InlineKeyboardButton(text=f"#{r['id']} — уровень {r['level']}",callback_data=f'business_manage:{r["id"]}')] for r in instances]; rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data=back)]); return InlineKeyboardMarkup(inline_keyboard=rows)
def back_keyboard(c): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад',callback_data=c)]])
def buyer_menu_keyboard():
    rows=[[InlineKeyboardButton(text=f"{i['emoji']} Продать {i['name'].lower()}",callback_data=f'resource_sell:{k}')] for k,i in RESOURCES.items()]; rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')]); return InlineKeyboardMarkup(inline_keyboard=rows)
