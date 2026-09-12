"""
Регистрация и вход в аккаунт (пошаговые сценарии на FSM).
"""
import re

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

import config
from database import queries
from database.database import db
from handlers.profile import show_profile
from services.security import hash_password, verify_password
from states.states import LoginStates, RegisterStates

router = Router()

NICKNAME_PATTERN = re.compile(r"^[A-Za-zА-Яа-яЁё0-9_]+$")


# --------------------------------------------------------------------------
# Регистрация
# --------------------------------------------------------------------------

@router.callback_query(F.data == "auth:register")
async def cb_register_start(callback: CallbackQuery, state: FSMContext) -> None:
    async with db.connect() as conn:
        existing = await queries.get_user_by_telegram_id(conn, callback.from_user.id)
    if existing is not None:
        await callback.answer("У вас уже есть аккаунт. Используйте /start", show_alert=True)
        return

    await state.set_state(RegisterStates.nickname)
    await callback.message.edit_text("👤 Введите ваш никнейм:")
    await callback.answer()


@router.message(RegisterStates.nickname)
async def register_nickname(message: Message, state: FSMContext) -> None:
    nickname = message.text.strip() if message.text else ""

    if not (config.NICKNAME_MIN_LENGTH <= len(nickname) <= config.NICKNAME_MAX_LENGTH):
        await message.answer(
            f"❌ Никнейм должен быть от {config.NICKNAME_MIN_LENGTH} "
            f"до {config.NICKNAME_MAX_LENGTH} символов. Попробуйте снова:"
        )
        return

    if not NICKNAME_PATTERN.match(nickname):
        await message.answer(
            "❌ Никнейм может содержать только буквы, цифры и знак подчёркивания. "
            "Попробуйте другой:"
        )
        return

    async with db.connect() as conn:
        existing = await queries.get_user_by_nickname(conn, nickname)

    if existing is not None:
        await message.answer("❌ Этот никнейм уже занят. Попробуйте другой.")
        return

    await state.update_data(nickname=nickname)
    await state.set_state(RegisterStates.age)
    await message.answer("🎂 Введите ваш возраст:")


@router.message(RegisterStates.age)
async def register_age(message: Message, state: FSMContext) -> None:
    raw_age = message.text.strip() if message.text else ""

    if not raw_age.isdigit():
        await message.answer("❌ Возраст должен быть числом. Попробуйте снова:")
        return

    age = int(raw_age)
    if not (config.AGE_MIN <= age <= config.AGE_MAX):
        await message.answer(
            f"❌ Возраст должен быть от {config.AGE_MIN} до {config.AGE_MAX} лет. Попробуйте снова:"
        )
        return

    await state.update_data(age=age)
    await state.set_state(RegisterStates.password)
    await message.answer("🔑 Придумайте пароль:")


@router.message(RegisterStates.password)
async def register_password(message: Message, state: FSMContext) -> None:
    password = message.text.strip() if message.text else ""

    # Удаляем сообщение с паролем из чата, чтобы он не оставался в истории
    try:
        await message.delete()
    except Exception:
        pass

    if not (config.PASSWORD_MIN_LENGTH <= len(password) <= config.PASSWORD_MAX_LENGTH):
        await message.answer(
            f"❌ Пароль должен быть от {config.PASSWORD_MIN_LENGTH} "
            f"до {config.PASSWORD_MAX_LENGTH} символов. Придумайте другой:"
        )
        return

    data = await state.get_data()
    nickname = data["nickname"]
    age = data["age"]

    password_hash, salt = hash_password(password)

    async with db.connect() as conn:
        # Финальная проверка на случай, если ник заняли, пока шла регистрация
        if await queries.get_user_by_nickname(conn, nickname) is not None:
            await state.clear()
            await message.answer("❌ Этот никнейм уже занят. Начните регистрацию заново: /start")
            return
        if await queries.get_user_by_telegram_id(conn, message.from_user.id) is not None:
            await state.clear()
            await message.answer("У вас уже есть аккаунт. Используйте /start")
            return

        referral_code = data.get("referral_code")
        user = await queries.create_user(
            conn,
            telegram_id=message.from_user.id,
            nickname=nickname,
            age=age,
            password_hash=password_hash,
            password_salt=salt,
            start_money=config.START_MONEY,
            start_stars=config.START_STARS,
        )
        if referral_code:
            inviter_id = await queries.apply_referral(conn, user.id, referral_code)
            if inviter_id:
                from services.quests import progress as quest_progress
                await queries.update_user_money(conn, inviter_id, 2000)
                await queries.update_user_stars(conn, inviter_id, 50)
                await queries.add_transaction(conn, inviter_id, 'referral', 'money', 2000, f'Награда за приглашение: {user.nickname}')
                await queries.add_transaction(conn, inviter_id, 'referral', 'stars', 50, f'Награда за приглашение: {user.nickname}')
                await quest_progress(conn, inviter_id, 1, 1)
                await conn.commit()

    await state.clear()
    await message.answer(f"✅ Регистрация завершена!\n\nДобро пожаловать, {user.nickname}! 🎉")
    await show_profile(message, user.id)


# --------------------------------------------------------------------------
# Вход
# --------------------------------------------------------------------------

@router.callback_query(F.data == "auth:login")
async def cb_login_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(LoginStates.nickname)
    await callback.message.edit_text("👤 Введите ваш никнейм:")
    await callback.answer()


@router.message(LoginStates.nickname)
async def login_nickname(message: Message, state: FSMContext) -> None:
    nickname = message.text.strip() if message.text else ""
    await state.update_data(nickname=nickname)
    await state.set_state(LoginStates.password)
    await message.answer("🔑 Введите ваш пароль:")


@router.message(LoginStates.password)
async def login_password(message: Message, state: FSMContext) -> None:
    password = message.text.strip() if message.text else ""

    try:
        await message.delete()
    except Exception:
        pass

    data = await state.get_data()
    nickname = data.get("nickname", "")

    async with db.connect() as conn:
        user = await queries.get_user_by_nickname(conn, nickname)

    # Намеренно не сообщаем отдельно, существует ли аккаунт — так безопаснее
    if user is None or not verify_password(password, user.password_salt, user.password_hash):
        await message.answer("❌ Неверный никнейм или пароль.")
        return

    if user.telegram_id != message.from_user.id:
        # Аккаунт привязан к другому Telegram ID — не даём войти
        await message.answer("❌ Неверный никнейм или пароль.")
        return

    await state.clear()
    await show_profile(message, user.id)
