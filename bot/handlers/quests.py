from aiogram import Router,F
from aiogram.filters import Command
from aiogram.types import Message,CallbackQuery
from database import queries
from database.database import db
from keyboards.quests import quests_keyboard
from services.quests import format_stars
router=Router()

def quest_status(row):
 if row['claimed']: return '✅ Выполнено'
 if row['completed']: return '🎁 Награда выдана'
 return f"⏳ {row['progress']}/{['1','1','1000','1','1'][row['id']-1]}"

async def quest_text(conn,user_id):
 rows=await queries.get_quest_rows(conn,user_id); out=['📋 <b>Задания</b>','']
 for r in rows:
  rewards=[]
  if r['reward_money']: rewards.append(f"💵 {r['reward_money']}$")
  if r['reward_stars']: rewards.append(f"⭐ {format_stars(int(r['reward_stars']*100))}")
  if r['reward_money_case']: rewards.append('🎁 1 кейс с $')
  out += [f"{r['title']}",r['description'],f"Прогресс: {quest_status(r)}",f"Награда: {', '.join(rewards)}",'']
 return '\n'.join(out)

@router.message(Command('quest'))
async def cmd_quest(message:Message):
 async with db.connect() as conn:
  user=await queries.get_user_by_telegram_id(conn,message.from_user.id)
  if not user: return await message.answer('Сначала зарегистрируйтесь через /start.')
  text=await quest_text(conn,user.id)
 await message.answer(text,reply_markup=quests_keyboard(),parse_mode='HTML')

@router.callback_query(F.data=='menu:quests')
async def cb_quests(callback):
 async with db.connect() as conn:
  user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
  if not user: return await callback.answer('Сначала войдите',show_alert=True)
  text=await quest_text(conn,user.id)
 await callback.message.edit_text(text,reply_markup=quests_keyboard(),parse_mode='HTML'); await callback.answer()
