import contextlib

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.main_menu import (
    get_main_menu_keyboard,
)
from app.bot.keyboards.subscriptions import get_cancel_keyboard
from app.bot.states import WAITING_FOR_URL
from app.bot.utils.url_parser import clean_and_validate_url
from app.core.logging import get_logger

logger = get_logger(__name__)


async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Обработчик команды /add или callback "menu_add"

    Запрашивает у пользователя ссылку на товар.
    Возвращает состояние WAITING_FOR_URL для ConversationHandler.
    """
    if not update.effective_user:
        logger.error("add_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        elif update.message:
            await update.message.reply_text(
                "Ошибка: не удалось получить информацию о пользователе."
            )
        return -1

    chat_id = update.effective_user.id
    logger.info("add_command_start", chat_id=chat_id)

    message = (
        "➕ Добавление подписки\n\n"
        "Отправьте ссылку на товар с Ozon.\n\n"
        "💡 Можно отправить:\n"
        "• Просто ссылку: https://ozon.ru/product/...\n"
        "• Поделиться из приложения Ozon\n\n"
        "Для отмены нажмите кнопку ниже:"
    )

    if update.callback_query:
        await update.callback_query.edit_message_text(
            message, reply_markup=get_cancel_keyboard()
        )
        context.user_data["add_request_message_id"] = (
            update.callback_query.message.message_id
        )
    elif update.message:
        await update.message.reply_text(message, reply_markup=get_cancel_keyboard())
        context.user_data["add_request_message_id"] = update.message.message_id

    return WAITING_FOR_URL


async def handle_url(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> int:
    """
    Обработчик получения URL от пользователя

    Валидирует URL и создаёт подписку.
    """
    if not update.effective_user or not update.message:
        logger.error("handle_url_no_user_or_message", update=update)
        return WAITING_FOR_URL

    chat_id = update.effective_user.id
    text = update.message.text
    logger.info("handle_url", chat_id=chat_id, text=text[:100])
    url, marketplace = clean_and_validate_url(text)

    if not url:
        await update.message.reply_text(
            "❌ Не удалось найти корректную ссылку в сообщении.\n\n"
            "Убедитесь, что вы отправили ссылку на товар "
            "с поддерживаемого маркетплейса (ozon.ru).\n\n"
            'Попробуйте ещё раз или нажмите "❌ Отмена".',
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_FOR_URL

    if not marketplace:
        await update.message.reply_text(
            f"❌ Маркетплейс не поддерживается.\n\n"
            f"Поддерживаемые маркетплейсы: Ozon (ozon.ru)\n\n"
            f"Отправленная ссылка: {url}\n\n"
            'Попробуйте ещё раз или нажмите "❌ Отмена".',
            reply_markup=get_cancel_keyboard(),
        )
        return WAITING_FOR_URL

    try:
        user_id = context.user_data.get("user_id")
        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id
                logger.info("user_id_cached", user_id=user_id)

            subscription_data = await client.create_subscription(
                user_id=user_id, marketplace=marketplace, product_url=url
            )

        subscription_id = subscription_data.get("id")
        product_name = subscription_data.get("product_name")
        current_price = subscription_data.get("current_price")
        logger.info(
            "subscription_created",
            subscription_id=subscription_id,
            user_id=user_id,
            product_url=url,
            marketplace=marketplace,
        )
        context.user_data["cached_subscriptions"] = None
        logger.info("subscriptions_cache_invalidated")
        with contextlib.suppress(Exception):
            await update.message.delete()

        success_message = "✅ Подписка успешно добавлена!\n\n"
        if product_name:
            success_message += f"📦 Товар: {product_name}\n"

        success_message += f"🔗 Ссылка: {url}\n"
        if current_price is not None:
            success_message += f"💰 Цена: {current_price} ₽\n"

        success_message += (
            "\n💡 Система будет проверять цену каждые 15 минут "
            "и уведомит вас при снижении."
        )
        request_message_id = context.user_data.get("add_request_message_id")
        if request_message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=request_message_id,
                text=success_message,
                reply_markup=get_main_menu_keyboard(),
            )
        else:
            await update.message.reply_text(
                success_message, reply_markup=get_main_menu_keyboard()
            )

        context.user_data.pop("add_request_message_id", None)
        return -1

    except Exception as e:
        logger.error("handle_url_failed", chat_id=chat_id, url=url, error=str(e))
        error_message = str(e)
        if "400" in error_message:
            await update.message.reply_text(
                "❌ Ошибка: некорректные данные. "
                "Проверьте ссылку и попробуйте снова.\n\n"
                'Попробуйте ещё раз или нажмите "❌ Отмена".',
                reply_markup=get_cancel_keyboard(),
            )
        elif "404" in error_message:
            await update.message.reply_text(
                "❌ Ошибка: товар не найден. Проверьте ссылку.\n\n"
                'Попробуйте ещё раз или нажмите "❌ Отмена".',
                reply_markup=get_cancel_keyboard(),
            )
        elif "500" in error_message:
            await update.message.reply_text(
                "❌ Ошибка сервера. Попробуйте позже.\n\n"
                'Попробуйте ещё раз или нажмите "❌ Отмена".',
                reply_markup=get_cancel_keyboard(),
            )
        else:
            await update.message.reply_text(
                "❌ Произошла ошибка при добавлении подписки. Попробуйте позже.\n\n"
                'Попробуйте ещё раз или нажмите "❌ Отмена".',
                reply_markup=get_cancel_keyboard(),
            )

        return WAITING_FOR_URL


async def cancel_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена добавления подписки. Возвращает пользователя в главное меню."""
    chat_id = update.effective_user.id if update.effective_user else None
    request_message_id = context.user_data.get("add_request_message_id")

    if request_message_id and chat_id:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=request_message_id,
            text="🏠 Главное меню\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )
    elif update.callback_query:
        await update.callback_query.edit_message_text(
            "🏠 Главное меню\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )
    elif update.message:
        await update.message.reply_text(
            "🏠 Главное меню\n\nВыберите действие:",
            reply_markup=get_main_menu_keyboard(),
        )

    context.user_data.pop("add_request_message_id", None)
    logger.info("cancel_add", chat_id=chat_id)
    return -1
