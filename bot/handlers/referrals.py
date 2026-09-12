from aiogram import F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from database import queries
from database.database import db
import config
from services.quests import format_stars

router=Router()

def referral_kb():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='🔗 Моя реферальная ссылка',callback_data='ref:link')],
        [InlineKeyboardButton(text='◀️ Назад',callback_data='back:main')],
    ])

async def render_ref(conn,user):
    st=await queries.get_referral_stats(conn,user.id)
    link=f"https://t.me/{config.BOT_USERNAME}?start={user.referral_code}" if config.BOT_USERNAME else f"/start {user.referral_code}"
    return ("👥 <b>Реферальная система</b>\n\n"
            "Приглашайте друзей и получайте награды!\n\n"
            "💵 Награда за друга: <b>2 000$</b>\n"
            "⭐ Награда за друга: <b>0.5 ⭐</b>\n\n"
            f"👥 Всего приглашено: <b>{st['invited']}</b>\n"
            f"✅ Зарегистрировалось: <b>{st['registered']}</b>\n"
            f"💵 Всего заработано: <b>{st['money']}$</b>\n"
            f"⭐ Всего заработано: <b>{format_stars(st['stars'])} ⭐</b>")

@router.callback_query(F.data=='menu:referrals')
async def menu(callback):
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
        text=await render_ref(conn,user)
    await callback.message.edit_text(text,reply_markup=referral_kb(),parse_mode='HTML'); await callback.answer()

@router.callback_query(F.data=='ref:link')
async def link(callback):
    async with db.connect() as conn:
        user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
        if not user: return await callback.answer('Сначала войдите в аккаунт',show_alert=True)
        link=f"https://t.me/{config.BOT_USERNAME}?start={user.referral_code}" if config.BOT_USERNAME else f"/start {user.referral_code}"
    await callback.message.edit_text(f'🔗 <b>Ваша реферальная ссылка:</b>\n\n<code>{link}</code>\n\nОтправьте её друзьям, чтобы получать награды.',reply_markup=referral_kb(),parse_mode='HTML'); await callback.answer()
