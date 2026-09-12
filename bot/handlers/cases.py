import asyncio,random
from aiogram import F,Router
from aiogram.types import CallbackQuery
from database import queries
from database.database import db
from database.queries import InsufficientFundsError
from keyboards.cases import cases_keyboard
from services.transactions import CURRENCY_MONEY,CURRENCY_STARS,TX_CASE,log_transaction
from services.quests import format_stars
router=Router()
MONEY_PRIZES=[(1000,40),(1500,30),(3000,15),(10000,10),(30000,5)]
STAR_PRIZES=[(10,70),(15,15),(25,10),(50,5)]

def weighted(items): return random.choices([x[0] for x in items],weights=[x[1] for x in items],k=1)[0]

def pick_text(items,stars=False):
 x=weighted(items); return f'⭐ {x} звёзд' if stars else f'💵 {x}$',x

@router.callback_query(F.data=='menu:cases')
async def menu(callback,state):
 async with db.connect() as conn:
  user=await queries.get_user_by_telegram_id(conn,callback.from_user.id); inv=await queries.get_case_inventory(conn,user.id) if user else None
 if not user: return await callback.answer('Сначала войдите в аккаунт: /start',show_alert=True)
 await callback.message.edit_text(f'🎁 <b>Кейсы</b>\n\n💵 Кейс с $ — открытие за ⭐ 1\n⭐ Кейс со звёздами — открытие за ⭐ 15\n\nДоступно кейсов: 💵 {inv["money_cases"]} | ⭐ {inv["star_cases"]}',reply_markup=cases_keyboard(inv['money_cases'],inv['star_cases']),parse_mode='HTML'); await callback.answer()

async def animate(message):
 for text in ('🎁 Открываем кейс...','🎁 Открываем кейс... 🔄','🎁 Открываем кейс... 🔄🔄'):
  await message.edit_text(text); await asyncio.sleep(.35)

@router.callback_query(F.data=='case:money')
async def money_case(callback):
 async with db.connect() as conn:
  user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
  if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
  inv=await queries.get_case_inventory(conn,user.id)
  if inv['money_cases']<=0: return await callback.answer('❌ У вас нет кейса с $. Получите его за задание.',show_alert=True)
  try:
   await queries.update_user_stars(conn,user.id,-100)
  except InsufficientFundsError: return await callback.answer('❌ Нужно 1 ⭐',show_alert=True)
  if not await queries.consume_money_case(conn,user.id):
   await conn.rollback(); return await callback.answer('❌ Кейс недоступен.',show_alert=True)
  prize_text,prize=pick_text(MONEY_PRIZES)
  await log_transaction(conn,user.id,TX_CASE,CURRENCY_STARS,-100,'Открытие кейса с $')
  await queries.update_user_money(conn,user.id,prize)
  await log_transaction(conn,user.id,TX_CASE,CURRENCY_MONEY,prize,f'Награда кейса: {prize}$')
  await conn.commit()
 await animate(callback.message); await callback.message.edit_text(f'🎉 <b>Кейс открыт!</b>\n\nВам выпало:\n\n<b>{prize_text}</b>',parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data=='case:stars')
async def star_case(callback):
 async with db.connect() as conn:
  user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
  if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
  try: await queries.update_user_stars(conn,user.id,-1500)
  except InsufficientFundsError: return await callback.answer('❌ Нужно 15 ⭐',show_alert=True)
  prize_text,prize=pick_text(STAR_PRIZES,True)
  await log_transaction(conn,user.id,TX_CASE,CURRENCY_STARS,-1500,'Открытие кейса со звёздами')
  await queries.update_user_stars(conn,user.id,prize*100)
  await log_transaction(conn,user.id,TX_CASE,CURRENCY_STARS,prize*100,f'Награда кейса: {prize} ⭐')
  await conn.commit()
 await animate(callback.message); await callback.message.edit_text(f'🎉 <b>Кейс открыт!</b>\n\nВам выпало:\n\n<b>{prize_text}</b>',parse_mode='HTML'); await callback.answer()
