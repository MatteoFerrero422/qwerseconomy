from decimal import Decimal as D
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, InlineKeyboardButton, InlineKeyboardMarkup
from database import queries
from database.database import db
from database.queries import InsufficientFundsError
from keyboards.shop import *
from services.businesses import *
from services.resources import get_resource_info
from services.transactions import CURRENCY_MONEY,TX_PURCHASE,TX_DEBIT,log_transaction
from services.quests import progress as quest_progress
from states.states import BuyResourceStates

router=Router()

def fmt(v):
    value = D(str(v))
    text = format(value, 'f')
    if '.' in text:
        text = text.rstrip('0').rstrip('.')
    return text

def money_price(info): return info.get('purchase_money',0)

@router.callback_query(F.data=='menu:shop')
async def cb_shop_menu(callback,state):
    await state.clear(); await callback.message.edit_text('🛒 <b>Магазин</b>\n\nРесурсы и бизнесы.',reply_markup=shop_menu_keyboard(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data=='shop:resources')
async def cb_shop_resources(callback,state):
    await callback.message.edit_text('📦 Выберите ресурс:',reply_markup=resource_list_keyboard('resource_buy','menu:shop')); await callback.answer()

@router.callback_query(F.data.startswith('resource_buy:'))
async def cb_resource_buy_select(callback,state):
    t=callback.data.split(':',1)[1]; info=get_resource_info(t)
    if not info: return await callback.answer('Неизвестный ресурс',show_alert=True)
    await state.update_data(resource_type=t); await state.set_state(BuyResourceStates.quantity)
    await callback.message.edit_text(f"{info['emoji']} <b>{info['name']}</b>\n\nЦена: <code>1$</code> за 1 шт.\n\nУкажите количество:",reply_markup=back_keyboard('shop:resources'),parse_mode='HTML'); await callback.answer()

@router.message(BuyResourceStates.quantity)
async def process_resource_quantity(message,state):
    data=await state.get_data(); t=data.get('resource_type'); info=get_resource_info(t)
    if not info: return
    raw=(message.text or '').strip()
    if not raw.isdigit() or int(raw)<=0: return await message.answer('❌ Введите положительное целое число:')
    qty=int(raw); total=qty*info['buy_price']
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,message.from_user.id)
        if not user: await state.clear(); return await message.answer('Сначала войдите в аккаунт: /start')
        try:
            await queries.update_user_money(conn,user.id,-total); await queries.update_resource(conn,user.id,t,qty)
            await log_transaction(conn,user.id,TX_PURCHASE,CURRENCY_MONEY,-total,f'Покупка {qty} x {info["name"]}')
            r=await queries.get_resources(conn,user.id)
            if r.stone>=5000 and r.ore>=5000 and r.wood>=2500: await quest_progress(conn,user.id,4,1)
            await conn.commit()
        except InsufficientFundsError: await conn.rollback(); return await message.answer('❌ Недостаточно денег!')
    await state.clear(); await message.answer(f'✅ Куплено: <code>{qty}</code> {info["emoji"]} {info["name"]}\nПотрачено: <code>{total}$</code>',parse_mode='HTML')

@router.callback_query(F.data=='shop:businesses')
async def cb_shop_businesses(callback,state):
    await callback.message.edit_text('🏪 <b>Бизнесы</b>\n\nВыберите бизнес:',reply_markup=business_list_keyboard(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('business_view:'))
async def cb_business_view(callback,state):
    t=callback.data.split(':',1)[1]; info=get_business_info(t)
    if not info: return await callback.answer('Неизвестный бизнес',show_alert=True)
    resources='\n'.join(f"{get_resource_info(k)['emoji']} {get_resource_info(k)['name']}: <code>{v}</code>" for k,v in info.get('purchase_resources',{}).items()) or 'Нет'
    purchase_level=business_purchase_level(info)
    price=f"<code>{info.get('purchase_money',0)}$</code>" if info.get('purchase_money',0) else 'Ресурсами'
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        owned=await queries.get_business_instances(conn,user.id,t) if user else []
    buttons=[[InlineKeyboardButton(text='✅ Купить',callback_data=f'business_confirm:{t}')]]
    if owned: buttons.append([InlineKeyboardButton(text=f'📋 Мои ({len(owned)})',callback_data=f'business_my:{t}')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад',callback_data='shop:businesses')])
    if info.get('max_level') == 7:
        level_info='\n'.join(
            f"L{lvl}: {fmt(BUSINESS_LEVELS[lvl]['income_money'])}$/мин"
            + (f" + {fmt(BUSINESS_LEVELS[lvl]['income_stars'])} ⭐/мин" if BUSINESS_LEVELS[lvl]['income_stars'] else '')
            + ("  ← уровень покупки" if lvl == purchase_level else '')
            for lvl in range(1,8)
        )
    else:
        level_info='\n'.join(f"L{lvl}: {fmt(info.get('income_by_level',{}).get(lvl,0))}$/мин" for lvl in range(1,info.get('max_level',1)+1))
    await callback.message.edit_text(f"{info['emoji']} <b>{info['name']}</b>\n\nЦена покупки: {price}\nУровень после покупки: <code>{purchase_level}</code>\n{resources}\n\n<b>Общая таблица уровней:</b>\n{level_info}",reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('business_confirm:'))
async def cb_business_confirm(callback,state):
    t=callback.data.split(':',1)[1]; info=get_business_info(t)
    if not info: return await callback.answer('Неизвестный бизнес',show_alert=True)
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        if not user: return await callback.answer('Сначала войдите в аккаунт: /start',show_alert=True)
        try:
            if info.get('purchase_money',0): await queries.update_user_money(conn,user.id,-info['purchase_money'])
            for r,qty in info.get('purchase_resources',{}).items(): await queries.update_resource(conn,user.id,r,-qty)
            await queries.add_business(conn,user.id,t,1,level=business_purchase_level(info))
            await log_transaction(conn,user.id,TX_PURCHASE,CURRENCY_MONEY,-info.get('purchase_money',0),f'Покупка бизнеса: {info["name"]}')
            if t=='stall': await quest_progress(conn,user.id,2,1)
            if t=='factory': await quest_progress(conn,user.id,5,1)
            await conn.commit()
        except InsufficientFundsError:
            await conn.rollback(); return await callback.answer('❌ Недостаточно денег или ресурсов!',show_alert=True)
    await callback.message.edit_text(f'✅ {info["name"]} куплен!',parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('business_my:'))
async def cb_business_my(callback,state):
    t=callback.data.split(':',1)[1]
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); rows=await queries.get_business_instances(conn,user.id,t) if user else []
    if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
    info=get_business_info(t)
    await callback.message.edit_text(f"{info['emoji']} <b>{info['name']}</b>\n\nВыберите конкретный экземпляр:",reply_markup=business_instances_keyboard(rows),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('business_manage:'))
async def cb_business_manage(callback,state):
    iid=int(callback.data.split(':',1)[1])
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); row=await queries.get_business_instance(conn,user.id,iid) if user else None
        if not row: return await callback.answer('Бизнес не найден',show_alert=True)
        row,_=await queries.finish_business_upgrade_if_ready(conn,user.id,iid); await conn.commit()
    info=get_business_info(row['business_type']); maxlvl=business_max_level(info)
    inc=business_income_per_minute(info,row['level']); stars=business_stars_per_minute(info,row['level'])
    text=f"{info['emoji']} <b>{info['name']} №{iid}</b>\n\nУровень: <code>{row['level']}</code>/{maxlvl}\n💵 Доход: <code>{fmt(inc)}$/мин</code>\n⭐ Игровой доход: <code>{fmt(stars)} ⭐/мин</code>"
    if row['upgrade_ends_at']:
        from datetime import datetime, timezone
        left=max(0,int((datetime.fromisoformat(row['upgrade_ends_at'])-datetime.now(timezone.utc)).total_seconds()))
        text += f"\n\n🔨 <b>Улучшение идёт</b>\n⏳ Осталось: <code>{left//3600:02d}:{(left%3600)//60:02d}:{left%60:02d}</code>"
    buttons=[]
    if row['level']<maxlvl and not row['upgrade_ends_at']:
        new=row['level']+1; buttons.append([InlineKeyboardButton(text=f'⬆️ Улучшить за {UPGRADE_COSTS[new]}$',callback_data=f'upgrade:{iid}')])
    buttons.append([InlineKeyboardButton(text='◀️ Назад',callback_data=f'business_my:{row["business_type"]}')])
    await callback.message.edit_text(text,reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('upgrade:'))
async def cb_upgrade(callback,state):
    iid=int(callback.data.split(':',1)[1])
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); row=await queries.get_business_instance(conn,user.id,iid) if user else None
        if not row: return await callback.answer('Бизнес не найден',show_alert=True)
        info=get_business_info(row['business_type']); maxlvl=business_max_level(info)
        if row['level']>=maxlvl: return await callback.answer('Достигнут максимальный уровень',show_alert=True)
        if row['upgrade_ends_at']: return await callback.answer('Этот бизнес уже улучшается',show_alert=True)
        new=row['level']+1; cost=UPGRADE_COSTS[new]; seconds=UPGRADE_TIMES[new]
        try: await queries.update_user_money(conn,user.id,-cost); await queries.start_business_upgrade(conn,user.id,iid,new,seconds); await log_transaction(conn,user.id,TX_DEBIT,CURRENCY_MONEY,-cost,f'Улучшение бизнеса #{iid} до {new}'); await conn.commit()
        except InsufficientFundsError: await conn.rollback(); return await callback.answer('❌ Недостаточно денег',show_alert=True)
    if seconds==0:
        async with db.connect() as conn:
            await conn.execute("UPDATE business_instances SET level=%s,upgrade_started_at=NULL,upgrade_ends_at=NULL WHERE id=%s AND user_id=%s",(new,iid,user.id)); await conn.commit()
        return await callback.answer(f'✅ Улучшение до {new} уровня завершено!',show_alert=True)
    await callback.message.edit_text(f'🔨 <b>{info["name"]} улучшается</b>\n\nТекущий уровень: {row["level"]}\nНовый уровень: {new}\n\n⏳ Время: {seconds//60} мин.',parse_mode='HTML'); await callback.answer()
