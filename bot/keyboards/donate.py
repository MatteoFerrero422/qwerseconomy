from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from services.businesses import VIP, business_max_level, get_business_info, STAR_UPGRADE_COSTS

def donate_menu_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
      [InlineKeyboardButton(text='⭐ Пополнить звёзды',callback_data='donate:topup')],
      [InlineKeyboardButton(text='➖ Снять звёзды',callback_data='donate:withdraw')],
      [InlineKeyboardButton(text='👑 VIP',callback_data='donate:vip')],
      [InlineKeyboardButton(text='⬆️ Улучшение за ⭐',callback_data='donate:star_upgrade')],
      [InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')]])

def star_topup_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f'⭐ {x}',callback_data=f'topup:{x}') for x in (1,10,50)],[InlineKeyboardButton(text=f'⭐ {x}',callback_data=f'topup:{x}') for x in (100,500,1000)],[InlineKeyboardButton(text='✏️ Другое (1–1000)',callback_data='topup:custom')],[InlineKeyboardButton(text='◀️ Назад',callback_data='menu:donate')]])
def donate_back_keyboard(): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='◀️ Назад',callback_data='menu:donate')]])
def vip_list_keyboard():
    rows=[[InlineKeyboardButton(text=f"{info['name']} — {info['price']} ⭐ / 30 дней",callback_data=f'vip:{key}')] for key,info in VIP.items()]; rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data='menu:donate')]); return InlineKeyboardMarkup(inline_keyboard=rows)
def vip_confirm_keyboard(vip): return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Купить',callback_data=f'vip_buy:{vip}')],[InlineKeyboardButton(text='◀️ Назад',callback_data='donate:vip')]])
def star_upgrade_list_keyboard(instances):
    rows=[]
    for r in instances:
        info=get_business_info(r['business_type']); maxlvl=business_max_level(info)
        if r['level']<maxlvl:
            nxt=r['level']+1; cost=STAR_UPGRADE_COSTS.get(nxt)
            rows.append([InlineKeyboardButton(text=f"#{r['id']} {info['name']} L{r['level']}→L{nxt} ({cost} ⭐)",callback_data=f'star_upgrade:{r["id"]}')])
    rows.append([InlineKeyboardButton(text='◀️ Назад',callback_data='menu:donate')]); return InlineKeyboardMarkup(inline_keyboard=rows)
