from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.main_menu import get_main_menu_keyboard
from app.bot.keyboards.subscriptions import get_cancel_keyboard
from app.bot.states import WAITING_FOR_TARGET_PRICE
from app.core.logging import get_logger

logger = get_logger(__name__)


async def set_target_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Обработчик кнопки "🎯 Target"

    Запрашивает у пользователя target_price.
    Возвращает состояние WAITING_FOR_TARGET_PRICE для ConversationHandler.
    """
    if not update.effective_user:
        logger.error("set_target_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        return -1

    chat_id = update.effective_user.id
    query = update.callback_query

    if not query:
        return -1

    # Получаем subscription_id из callback_data
    callback_data = query.data
    if not callback_data.startswith("set_target_"):
        return -1

    subscription_id = int(callback_data.split("_")[-1])
    context.user_data["target_subscription_id"] = subscription_id

    logger.info("set_target_start", chat_id=chat_id, subscription_id=subscription_id)

    message = (
        "🎯 Установка целевой цены\n\n"
        "Отправьте цену в рублях, при достижении которой "
        "вы хотите получить уведомление.\n\n"
        "Примеры:\n"
        "• 1000\n"
        "• 1500.50\n\n"
        "Для отмены нажмите кнопку ниже:"
    )

    await query.edit_message_text(
        message,
        reply_markup=get_cancel_keyboard(),
    )

    return WAITING_FOR_TARGET_PRICE


async def handle_target_price(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Обработчик получения target_price от пользователя
    """
    if not update.effective_user or not update.message:
        logger.error("handle_target_price_no_user_or_message", update=update)
        return WAITING_FOR_TARGET_PRICE

    chat_id = update.effective_user.id
    text = update.message.text.strip()
    subscription_id = context.user_data.get("target_subscription_id")

    if not subscription_id:
        await update.message.reply_text(
            "❌ Ошибка: не найдена подписка. Попробуйте ещё раз.",
            reply_markup=get_main_menu_keyboard(),
        )
        return -1

    logger.info(
        "handle_target_price",
        chat_id=chat_id,
        text=text,
        subscription_id=subscription_id,
    )

    # Парсим цену
    try:
        target_price = Decimal(text.replace(",", "."))
        if target_price <= 0:
            raise ValueError("Цена должна быть положительной")
    except (InvalidOperation, ValueError) as e:
        logger.warning("invalid_target_price", chat_id=chat_id, text=text, error=str(e))
        await update.message.reply_text(
            "❌ Некорректная цена. Пожалуйста, отправьте число.\n\n"
            "Примеры:\n"
            "• 1000\n"
            "• 1500.50\n\n"
            "Для отмены нажмите кнопку ниже:",
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_FOR_TARGET_PRICE

    # Отправляем запрос к API
    try:
        user_id = context.user_data.get("user_id")
        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            await client.update_target_price(
                subscription_id=subscription_id,
                user_id=user_id,
                target_price=float(target_price),
            )

        logger.info(
            "target_price_updated",
            subscription_id=subscription_id,
            target_price=float(target_price),
        )

        # Инвалидируем кэш подписок
        context.user_data["cached_subscriptions"] = None

        await update.message.reply_text(
            f"✅ Целевая цена установлена: {target_price:,.2f} ₽\n\n"
            f"Вы получите уведомление когда цена опустится ниже этой цели.",
            reply_markup=get_main_menu_keyboard(),
        )

        return -1  # Завершаем ConversationHandler

    except Exception as e:
        logger.error(
            "handle_target_price_failed",
            chat_id=chat_id,
            subscription_id=subscription_id,
            error=str(e),
        )
        await update.message.reply_text(
            "❌ Произошла ошибка при установке целевой цены. Попробуйте позже.\n\n"
            "Для отмены нажмите кнопку ниже:",
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_FOR_TARGET_PRICE


async def cancel_set_target(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Отмена установки target_price
    """
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🏠 Главное меню\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )
    elif update.message:
        await update.message.reply_text(
            "🏠 Главное меню\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )

    logger.info(
        "cancel_set_target",
        chat_id=update.effective_user.id if update.effective_user else None,
    )
    return -1
