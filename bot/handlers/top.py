from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from database import queries
from database.database import db
from services.quests import format_stars
router=Router()

def top_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='💵 Топ по балансу',callback_data='top:money')],
        [InlineKeyboardButton(text='⭐ Топ по звёздам',callback_data='top:stars')],
        [InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')],
    ])

def medals(i): return {1:'🥇',2:'🥈',3:'🥉'}.get(i,f'{i}.')

async def text(conn,user_id,currency):
    top,own=await queries.get_top_users(conn,currency,10,user_id)
    title='💵 <b>ТОП по балансу</b>' if currency=='money' else '⭐ <b>ТОП по звёздам</b>'
    lines=[title,'']
    for i,r in enumerate(top,1):
        val=f"{r['value']}$" if currency=='money' else f"{format_stars(r['value'])} ⭐"
        lines.append(f"{medals(i)} <b>{r['nickname']}</b> — {val}")
    if own and own>10:
        # own position is included as a compact extra line below
        lines += ['',f'👤 Ваша позиция: <b>#{own}</b>']
    return '\n'.join(lines)

@router.callback_query(F.data=='menu:top')
async def menu(callback):
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
    if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
    await callback.message.edit_text('🏆 <b>Топ игроков</b>\n\nВыберите рейтинг:',reply_markup=top_kb(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data.startswith('top:'))
async def show(callback):
    currency=callback.data.split(':',1)[1]
    if currency not in ('money','stars'): return await callback.answer('Ошибка',show_alert=True)
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        if not user: return await callback.answer('Сначала войдите',show_alert=True)
        body=await text(conn,user.id,currency)
    await callback.message.edit_text(body,reply_markup=top_kb(),parse_mode='HTML'); await callback.answer()
