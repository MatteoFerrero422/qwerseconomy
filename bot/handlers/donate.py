from datetime import datetime, timezone, timedelta
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, PreCheckoutQuery
from aiogram.filters import StateFilter
from database import queries
from database.database import db
from database.queries import InsufficientFundsError
from keyboards.donate import *
from services.businesses import VIP, STAR_UPGRADE_COSTS, business_max_level, get_business_info
from services.payment import TOPUP_MIN,TOPUP_MAX,make_topup_payload,parse_topup_payload,invoice_prices
from services.transactions import CURRENCY_STARS,TX_DONATE_PURCHASE,TX_STAR_TOPUP,TX_STAR_WITHDRAW,log_transaction
from services.quests import format_stars
from states.states import StarsWithdrawStates,TopupStates
from aiogram.types import LabeledPrice

router=Router()

@router.callback_query(F.data=='menu:donate')
async def cb_donate_menu(callback,state):
    await state.clear(); await callback.message.edit_text('⭐ <b>Донат-магазин</b>',reply_markup=donate_menu_keyboard(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data=='donate:topup')
async def cb_topup(callback,state):
    await callback.message.edit_text('⭐ <b>Пополнение звёзд</b>\n\nВыберите сумму:',reply_markup=star_topup_keyboard(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data=='topup:custom')
async def cb_topup_custom(callback,state):
    await state.set_state(TopupStates.amount); await callback.message.edit_text('Введите количество ⭐ от 1 до 1000:'); await callback.answer()

async def send_topup_invoice(message,amount):
    payload=make_topup_payload(amount)
    await message.answer_invoice(title=f'Пополнение {amount} ⭐',description=f'Зачисление {amount} Telegram Stars на игровой баланс.',payload=payload,currency='XTR',prices=invoice_prices(amount),provider_token='')

@router.callback_query(F.data.startswith('topup:'))
async def cb_topup_amount(callback,state):
    try: amount=int(callback.data.split(':',1)[1])
    except ValueError: return await callback.answer('Некорректная сумма',show_alert=True)
    if not TOPUP_MIN<=amount<=TOPUP_MAX: return await callback.answer('Сумма должна быть от 1 до 1000 ⭐',show_alert=True)
    await send_topup_invoice(callback.message,amount); await callback.answer()

@router.message(TopupStates.amount)
async def custom_topup(message,state):
    raw=(message.text or '').strip()
    if not raw.isdigit() or not TOPUP_MIN<=int(raw)<=TOPUP_MAX: return await message.answer('❌ Введите целое число от 1 до 1000:')
    await state.clear(); await send_topup_invoice(message,int(raw))

@router.pre_checkout_query()
async def pre_checkout(query:PreCheckoutQuery):
    amount=parse_topup_payload(query.invoice_payload)
    if amount is None or query.currency!='XTR' or query.total_amount!=amount:
        await query.answer(ok=False,error_message='Платёж не прошёл проверку. Попробуйте создать новый счёт.')
        return
    await query.answer(ok=True)

@router.message(F.successful_payment)
async def successful_payment(message:Message):
    payment=message.successful_payment
    amount=parse_topup_payload(payment.invoice_payload)
    if amount is None or payment.currency!='XTR' or payment.total_amount!=amount: return
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,message.from_user.id)
        if not user: return
        # One telegram_payment_charge_id can credit the account only once.
        added=await queries.add_transaction(conn,user.id,TX_STAR_TOPUP,CURRENCY_STARS,amount*100,f'Пополнение {amount} ⭐',payment.telegram_payment_charge_id)
        if not added:
            await conn.rollback(); return
        await queries.update_user_stars(conn,user.id,amount*100)
        await conn.commit()
        new_balance=(user.stars+amount*100)
    await message.answer(f'✅ Оплата подтверждена.\n\nЗачислено: <b>{amount} ⭐</b>\nБаланс: <b>{format_stars(new_balance)} ⭐</b>',parse_mode='HTML')

@router.callback_query(F.data=='donate:withdraw')
async def cb_withdraw(callback,state):
    await state.set_state(StarsWithdrawStates.amount); await callback.message.edit_text('➖ Снятие ⭐\n\n🔧 В скором времени',reply_markup=donate_back_keyboard()); await callback.answer()

@router.message(StarsWithdrawStates.amount)
async def withdraw_disabled(message,state):
    await state.clear(); await message.answer('🔧 В скором времени')

@router.callback_query(F.data=='donate:vip')
async def cb_vip(callback,state):
    await callback.message.edit_text('👑 <b>VIP</b>\n\nВыберите привилегию:',reply_markup=vip_list_keyboard(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('vip:'))
async def cb_vip_view(callback,state):
    key=callback.data.split(':',1)[1]; info=VIP.get(key)
    if not info: return await callback.answer('Неизвестный VIP',show_alert=True)
    extra='\n🎁 Ежедневный подарок.' if key=='silver' else ('\n🎁 Ежемесячный подарок.' if key=='gold' else '')
    await callback.message.edit_text(f"👑 <b>{info['name']}</b>\n\nЦена: <b>{info['price']} ⭐ / 30 дней</b>\nБонус к доходу: <b>×{info['multiplier']}</b>{extra}",reply_markup=vip_confirm_keyboard(key),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('vip_buy:'))
async def cb_vip_buy(callback,state):
    key=callback.data.split(':',1)[1]; info=VIP.get(key)
    if not info: return await callback.answer('Неизвестный VIP',show_alert=True)
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        if not user: return await callback.answer('Сначала войдите в аккаунт: /start',show_alert=True)
        try:
            await queries.clear_vip_if_expired(conn,user.id)
            user=await queries.get_user_by_id(conn,user.id)
            await queries.update_user_stars(conn,user.id,-info['price']*100)
            now=datetime.now(timezone.utc); old=datetime.fromisoformat(user.vip_expires_at) if user.vip_expires_at and user.vip_type else now
            if old<now: old=now
            expires=old+timedelta(days=30)
            # A higher VIP replaces a lower one. Same/higher VIP extends its period.
            rank={'bronze':1,'silver':2,'gold':3}
            if user.vip_type and rank.get(user.vip_type,0)>rank[key]:
                await conn.rollback(); return await callback.answer('❌ Нельзя заменить более высокий VIP на более низкий.',show_alert=True)
            await queries.set_vip(conn,user.id,key,expires.isoformat())
            await log_transaction(conn,user.id,TX_DONATE_PURCHASE,CURRENCY_STARS,-info['price']*100,f'Покупка {info["name"]} на 30 дней')
            await conn.commit()
        except InsufficientFundsError: await conn.rollback(); return await callback.answer('❌ Недостаточно ⭐',show_alert=True)
    await callback.message.edit_text(f'✅ {info["name"]} активирован до {expires.strftime("%d.%m.%Y %H:%M UTC")}.',reply_markup=donate_back_keyboard()); await callback.answer()

@router.callback_query(F.data=='donate:star_upgrade')
async def cb_star_upgrade(callback,state):
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); instances=await queries.get_business_instances(conn,user.id) if user else []
    if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
    await callback.message.edit_text('⬆️ <b>Мгновенное улучшение за ⭐</b>\n\nВыберите конкретный бизнес:',reply_markup=star_upgrade_list_keyboard(instances),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('star_upgrade:'))
async def cb_star_upgrade_instance(callback,state):
    iid=int(callback.data.split(':',1)[1])
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); row=await queries.get_business_instance(conn,user.id,iid) if user else None
        if not row or row['level']>=business_max_level(get_business_info(row['business_type'])): return await callback.answer('Недоступно',show_alert=True)
        new=row['level']+1; cost=STAR_UPGRADE_COSTS[new]*100
        try:
            await queries.update_user_stars(conn,user.id,-cost)
            await conn.execute("UPDATE business_instances SET level=%s,upgrade_started_at=NULL,upgrade_ends_at=NULL WHERE id=%s AND user_id=%s",(new,iid,user.id))
            await log_transaction(conn,user.id,TX_DONATE_PURCHASE,CURRENCY_STARS,-cost,f'Мгновенное улучшение бизнеса #{iid} до {new}')
            await conn.commit()
        except InsufficientFundsError: await conn.rollback(); return await callback.answer('❌ Недостаточно ⭐',show_alert=True)
    await callback.answer(f'✅ Бизнес улучшен до уровня {new}',show_alert=True)
