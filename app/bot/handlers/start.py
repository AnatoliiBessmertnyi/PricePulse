from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.main_menu import get_main_menu_keyboard
from app.core.logging import get_logger

logger = get_logger(__name__)


async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик команды /start

    Регистрирует пользователя и показывает главное меню с кнопками навигации.
    """
    if not update.effective_user:
        logger.error("start_no_user", update=update)
        await update.message.reply_text(
            "Ошибка: не удалось получить информацию о пользователе."
        )
        return

    chat_id = update.effective_user.id
    username = update.effective_user.username
    logger.info("start_command", chat_id=chat_id, username=username)

    try:
        async with HTTPClient() as client:
            user_data = await client.create_user(chat_id=chat_id, username=username)

        user_id = user_data.get("id")
        chat_id_response = user_data.get("chat_id")
        username_response = user_data.get("username")
        logger.info(
            "user_registered",
            user_id=user_id,
            chat_id=chat_id_response,
            username=username_response,
        )
        greeting = f"Привет, {username_response or 'пользователь'}! 👋\n\n"
        greeting += "Добро пожаловать в PricePulse — систему отслеживания цен!\n\n"
        greeting += "🎯 Что я умею:\n"
        greeting += "• Отслеживать цены на товары\n"
        greeting += "• Уведомлять о снижении цен\n"
        greeting += "• Управлять вашими подписками\n\n"
        greeting += "Выберите действие:"
        await update.message.reply_text(greeting, reply_markup=get_main_menu_keyboard())

    except Exception as e:
        logger.error(
            "start_command_failed",
            chat_id=chat_id,
            error=str(e),
        )
        await update.message.reply_text(
            "Произошла ошибка при регистрации. Попробуйте позже."
        )
