"""
Скупщик: продажа ресурсов игрока за деньги.
"""
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database import queries
from database.database import db
from database.queries import InsufficientFundsError
from keyboards.shop import back_keyboard, buyer_menu_keyboard
from services.resources import get_resource_info
from services.transactions import CURRENCY_MONEY, TX_SALE, log_transaction
from states.states import SellResourceStates

router = Router()


@router.callback_query(F.data == "menu:buyer")
async def cb_buyer_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text(
        "💰 <b>Скупщик</b>\n\nЗдесь можно продать имеющиеся ресурсы.",
        reply_markup=buyer_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("resource_sell:"))
async def cb_resource_sell_select(callback: CallbackQuery, state: FSMContext) -> None:
    resource_type = callback.data.split(":", 1)[1]
    info = get_resource_info(resource_type)
    if info is None:
        await callback.answer("Неизвестный ресурс", show_alert=True)
        return

    async with db.connect() as conn:
        user = await queries.get_user_by_telegram_id(conn, callback.from_user.id)
        if user is None:
            await callback.answer("Сначала войдите в аккаунт: /start", show_alert=True)
            return
        resources = await queries.get_resources(conn, user.id)

    owned = getattr(resources, resource_type)

    await state.update_data(resource_type=resource_type)
    await state.set_state(SellResourceStates.quantity)
    await callback.message.edit_text(
        f"{info['emoji']} <b>Продажа {info['name'].lower()}</b>\n\n"
        f"Цена: <code>{info['sell_price']}$</code> за 1 шт.\n\n"
        f"У вас: <code>{owned}</code> шт.\n\n"
        "Введите количество:",
        reply_markup=back_keyboard("menu:buyer"),
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(SellResourceStates.quantity)
async def process_sell_quantity(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    resource_type = data["resource_type"]
    info = get_resource_info(resource_type)

    raw_qty = message.text.strip() if message.text else ""
    if not raw_qty.isdigit() or int(raw_qty) <= 0:
        await message.answer("❌ Введите положительное целое число:")
        return

    quantity = int(raw_qty)

    async with db.connect() as conn:
        user = await queries.get_user_by_telegram_id(conn, message.from_user.id)
        if user is None:
            await message.answer("Сначала войдите в аккаунт: /start")
            await state.clear()
            return

        resources = await queries.get_resources(conn, user.id)
        owned = getattr(resources, resource_type)

        if owned < quantity:
            await message.answer(
                f"❌ У вас недостаточно ресурса!\n\nЕсть: <code>{owned}</code>, "
                f"хотите продать: <code>{quantity}</code>",
                parse_mode="HTML",
            )
            return

        total_income = info["sell_price"] * quantity

        try:
            await queries.update_resource(conn, user.id, resource_type, -quantity)
            await queries.update_user_money(conn, user.id, total_income)
            await log_transaction(
                conn,
                user.id,
                TX_SALE,
                CURRENCY_MONEY,
                total_income,
                f"Продажа {quantity} x {info['name']}",
            )
            await conn.commit()
        except InsufficientFundsError:
            await conn.rollback()
            await message.answer("❌ У вас недостаточно ресурса!")
            return

    await state.clear()
    await message.answer(
        "✅ Продажа завершена!\n\n"
        f"Продано: <code>{quantity}</code> {info['emoji']}\n"
        f"Получено: <code>{total_income}$</code>",
        parse_mode="HTML",
    )

    from handlers.profile import show_profile

    await show_profile(message, user.id)
