from datetime import datetime,timezone
from aiogram import F,Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery,Message
from database import queries
from database.database import db
from keyboards.main import main_menu_keyboard
import config
from services.economy import calculate_income_per_minute
from services.quests import format_stars
router=Router()

def vip_remaining(user):
    if not user.vip_type or not user.vip_expires_at: return None
    try:
        end=datetime.fromisoformat(user.vip_expires_at); left=max(0,int((end-datetime.now(timezone.utc)).total_seconds()))
        if left<=0:return None
        return left
    except ValueError:return None

def format_profile_text(user,resources,businesses,cases):
    from services.businesses import get_business_info, business_income_per_minute, vip_multiplier
    from decimal import Decimal
    base=sum((business_income_per_minute(get_business_info(b.business_type), b.level)*b.quantity for b in businesses if get_business_info(b.business_type)), Decimal('0'))
    income=base*Decimal(str(vip_multiplier(user.vip_type,user.vip_expires_at)))*60
    income_text=format(income,'f').rstrip('0').rstrip('.')
    referral=(f"<a href='https://t.me/{config.BOT_USERNAME}?start={user.referral_code}'>пригласить друга</a>" if config.BOT_USERNAME else f"<code>{user.referral_code}</code>")
    count=sum(b.quantity for b in businesses); vip=vip_remaining(user)
    vip_text=f"VIP {user.vip_type.title()}\n⏳ Осталось: {vip//86400} дн. {(vip%86400)//3600} ч." if vip else 'Нет'
    return (f"👤 <b>Профиль</b>\n\n👤 Никнейм: <code>{user.nickname}</code>\n\n"
            f"💵 Деньги: <code>{user.money}$</code>\n"
            f"⭐ Звёзды: <code>{format_stars(user.stars)} ⭐</code>\n"
            f"📦 <b>Ресурсы</b>\n\n🪨 Камень: <code>{resources.stone}</code>\n🌲 Дерево: <code>{resources.wood}</code>\n🌾 Еда: <code>{resources.food}</code>\n⛏️ Руда: <code>{resources.ore}</code>\n\n"
            f"🛡 Привилегия: <code>{vip_text}</code>\n🏠 Дом: <code>{user.house_id if user.house_id else 'Нет'}</code>\n"
            f"🏭 Бизнесов: <code>{count}</code>\n💰 Доход в час: <code>{income_text}$</code>\n\n"
            f"🎁 Кейсы: <code>{cases['money_cases']} 💵 / {cases['star_cases']} ⭐</code>\n\n"
            f"🔗 Реферальная ссылка: {referral}")

async def render_profile(user_id):
    async with db.connect() as conn:
        user=await queries.get_user_by_id(conn,user_id); resources=await queries.get_resources(conn,user_id); businesses=await queries.get_businesses(conn,user_id); cases=await queries.get_case_inventory(conn,user_id)
    return format_profile_text(user,resources,businesses,cases)

async def show_profile(message,user_id): await message.answer(await render_profile(user_id),reply_markup=main_menu_keyboard(),parse_mode='HTML')
async def edit_to_profile(callback,user_id): await callback.message.edit_text(await render_profile(user_id),reply_markup=main_menu_keyboard(),parse_mode='HTML')
async def _get_authorized_user_id(callback,state):
    async with db.connect() as conn: user=await queries.get_user_by_telegram_id(conn,callback.from_user.id)
    if not user: await callback.answer('Сначала войдите в аккаунт: /start',show_alert=True); return None
    return user.id
@router.callback_query(F.data=='back:main')
async def cb_back_main(callback,state):
    await state.clear(); uid=await _get_authorized_user_id(callback,state)
    if uid is not None: await edit_to_profile(callback,uid); await callback.answer()
