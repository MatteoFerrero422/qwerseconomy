"""
Обработка команды /start — точка входа в бота.
"""
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from database import queries
from database.database import db
from handlers.profile import show_profile

from keyboards.main import start_keyboard

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    parts=(message.text or "").split(maxsplit=1)
    referral_code=parts[1].strip() if len(parts)==2 and parts[1].startswith("ref_") else None
    if referral_code:
        await state.update_data(referral_code=referral_code)

    async with db.connect() as conn:
        user = await queries.get_user_by_telegram_id(conn, message.from_user.id)

    if user is not None:
        await show_profile(message, user.id)
        return

    await message.answer(
        "Добро пожаловать в экономическую игру! 💰\n\nВыберите действие:",
        reply_markup=start_keyboard(),
    )
