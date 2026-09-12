from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from database import queries
from database.database import db
from database.queries import InsufficientFundsError
import config

router=Router()

def is_admin(message): return message.from_user.id in config.ADMIN_IDS
async def get_admin(conn,telegram_id): return await queries.get_user_by_telegram_id(conn,telegram_id)

def usage(cmd):
    return {
        'givemoney':'/givemoney ник количество','takemoney':'/takemoney ник количество',
        'givestars':'/givestars ник количество','takestars':'/takestars ник количество',
        'reset':'/reset ник','uplvlfactory':'/uplvlfactory ник ID_бизнеса уровень'
    }[cmd]

async def target_by_nick(conn,nick): return await queries.get_user_by_nickname(conn,nick)

async def ensure_admin(message):
    if not is_admin(message): return False
    return True

async def log_admin(conn,message,command,target,value):
    admin=await get_admin(conn,message.from_user.id)
    admin_nick=admin.nickname if admin else str(message.from_user.id)
    await queries.add_admin_log(conn,message.from_user.id,admin_nick,command,target.id if target else None,target.nickname if target else None,str(value))

@router.message(Command('givemoney'))
async def givemoney(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=3 or not a[2].isdigit() or int(a[2])<=0: return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("givemoney")}</code>')
    amount=int(a[2])
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
        if not target: return await message.answer('❌ Игрок не найден.')
        await queries.update_user_money(conn,target.id,amount); await log_admin(conn,message,'/givemoney',target,amount); await queries.add_transaction(conn,target.id,'admin_givemoney','money',amount,f'Админ: {message.from_user.id}'); await conn.commit()
    await message.answer(f'✅ Игроку <b>{target.nickname}</b> выдано <b>{amount}$</b>.',parse_mode='HTML')

@router.message(Command('takemoney'))
async def takemoney(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=3 or not a[2].isdigit() or int(a[2])<=0: return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("takemoney")}</code>')
    amount=int(a[2])
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
        if not target: return await message.answer('❌ Игрок не найден.')
        try: await queries.update_user_money(conn,target.id,-amount)
        except InsufficientFundsError: return await message.answer('❌ Нельзя снять больше текущего баланса.')
        await log_admin(conn,message,'/takemoney',target,-amount); await queries.add_transaction(conn,target.id,'admin_takemoney','money',-amount,f'Админ: {message.from_user.id}'); await conn.commit()
    await message.answer(f'✅ У игрока <b>{target.nickname}</b> снято <b>{amount}$</b>.',parse_mode='HTML')

@router.message(Command('givestars'))
async def givestars(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=3 or not a[2].isdigit() or int(a[2])<=0: return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("givestars")}</code>')
    amount=int(a[2]); units=amount*100
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
        if not target: return await message.answer('❌ Игрок не найден.')
        await queries.update_user_stars(conn,target.id,units); await log_admin(conn,message,'/givestars',target,amount); await queries.add_transaction(conn,target.id,'admin_givestars','stars',units,f'Админ: {message.from_user.id}'); await conn.commit()
    await message.answer(f'✅ Игроку <b>{target.nickname}</b> выдано <b>{amount} ⭐</b>.',parse_mode='HTML')

@router.message(Command('takestars'))
async def takestars(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=3 or not a[2].isdigit() or int(a[2])<=0: return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("takestars")}</code>')
    amount=int(a[2]); units=amount*100
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
        if not target: return await message.answer('❌ Игрок не найден.')
        try: await queries.update_user_stars(conn,target.id,-units)
        except InsufficientFundsError: return await message.answer('❌ Нельзя снять больше текущего баланса ⭐.')
        await log_admin(conn,message,'/takestars',target,-amount); await queries.add_transaction(conn,target.id,'admin_takestars','stars',-units,f'Админ: {message.from_user.id}'); await conn.commit()
    await message.answer(f'✅ У игрока <b>{target.nickname}</b> снято <b>{amount} ⭐</b>.',parse_mode='HTML')

@router.message(Command('reset'))
async def reset(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=2: return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("reset")}</code>')
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
    if not target: return await message.answer('❌ Игрок не найден.')
    kb=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Подтвердить',callback_data=f'admin_reset_yes:{target.id}'),InlineKeyboardButton(text='❌ Отмена',callback_data='admin_reset_no')]])
    await message.answer(f'⚠️ Вы действительно хотите полностью сбросить прогресс игрока <b>"{target.nickname}"</b>?\n\nЭто действие нельзя отменить.',reply_markup=kb,parse_mode='HTML')

@router.callback_query(lambda c: c.data=='admin_reset_no')
async def reset_no(callback):
    if callback.from_user.id not in config.ADMIN_IDS: return await callback.answer('Нет доступа',show_alert=True)
    await callback.message.edit_text('❌ Сброс отменён.'); await callback.answer()

@router.callback_query(lambda c: c.data.startswith('admin_reset_yes:'))
async def reset_yes(callback):
    if callback.from_user.id not in config.ADMIN_IDS: return await callback.answer('Нет доступа',show_alert=True)
    uid=int(callback.data.split(':',1)[1])
    async with db.connect() as conn:
        target=await queries.get_user_by_id(conn,uid)
        if not target: return await callback.answer('Игрок не найден',show_alert=True)
        await queries.reset_player(conn,uid); await log_admin(conn,callback,'/reset',target,'full reset'); await conn.commit()
    await callback.message.edit_text(f'✅ Прогресс игрока <b>{target.nickname}</b> полностью сброшен.',parse_mode='HTML'); await callback.answer()

@router.message(Command('uplvlfactory'))
async def uplvl(message):
    if not await ensure_admin(message): return
    a=(message.text or '').split()
    if len(a)!=4 or not a[2].isdigit() or not a[3].isdigit() or int(a[2])<=0 or int(a[3])<1 or int(a[3])>7:
        return await message.answer(f'❌ Неверный формат команды.\n\nИспользование:\n<code>{usage("uplvlfactory")}</code>')
    business_id=int(a[2]); level=int(a[3])
    async with db.connect() as conn:
        target=await target_by_nick(conn,a[1])
        if not target: return await message.answer('❌ Игрок не найден.')
        row=await queries.get_business_instance(conn,target.id,business_id)
        if not row: return await message.answer('❌ Бизнес с таким ID не найден у игрока.')
        max_level=7
        if level>max_level: return await message.answer(f'❌ Для этого бизнеса максимальный уровень: {max_level}.')
        await conn.execute("UPDATE business_instances SET level=%s,upgrade_started_at=NULL,upgrade_ends_at=NULL WHERE id=%s AND user_id=%s",(level,business_id,target.id))
        await log_admin(conn,message,'/uplvlfactory',target,f'business_id={business_id}; level={level}')
        await conn.commit()
    await message.answer(f'✅ Бизнес <b>#{business_id}</b> игрока <b>{target.nickname}</b> установлен на уровень <b>{level}</b>.',parse_mode='HTML')
