import asyncio
import contextlib

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.handlers.add import add_command
from app.bot.handlers.delete import confirm_delete, delete_command, execute_delete
from app.bot.handlers.help import help_command
from app.bot.handlers.list import list_command
from app.bot.keyboards.main_menu import get_main_menu_keyboard
from app.core.logging import get_logger

logger = get_logger(__name__)

# Количество подписок на странице для пагинации
SUBSCRIPTIONS_PER_PAGE = 5


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик нажатий на inline кнопки

    Роутинг callback queries к соответствующим обработчикам.
    """
    query = update.callback_query
    if not query:
        return

    await query.answer("⏳")
    callback_data = query.data
    chat_id = query.from_user.id if query.from_user else None
    logger.info("callback_received", chat_id=chat_id, callback_data=callback_data)

    try:
        # Главное меню
        if callback_data == "back_main":
            await query.edit_message_text(
                "🏠 Главное меню\n\nВыберите действие:",
                reply_markup=get_main_menu_keyboard(),
            )

        # Меню - Мои подписки
        elif callback_data == "menu_list":
            context.user_data["list_page"] = 0
            await list_command(update, context)

        # Меню - Добавить товар
        elif callback_data == "menu_add":
            await add_command(update, context)

        # Меню - Удалить подписку
        elif callback_data == "menu_delete":
            context.user_data["delete_page"] = 0
            await delete_command(update, context)

        # Меню - Помощь
        elif callback_data == "menu_help":
            await help_command(update, context)

        # Отмена добавления подписки
        elif callback_data == "cancel_add":
            await query.edit_message_text(
                "🏠 Главное меню\n\nВыберите действие:",
                reply_markup=get_main_menu_keyboard(),
            )

        # Обновление списка подписок
        elif callback_data == "refresh_list":
            context.user_data["list_page"] = 0
            context.user_data["is_refresh"] = True
            await list_command(update, context)

        # Пагинация списка подписок
        elif callback_data.startswith("page_view_"):
            page = int(callback_data.split("_")[-1])
            context.user_data["list_page"] = page
            await list_command(update, context)

        # Пагинация списка удаления
        elif callback_data.startswith("page_delete_"):
            page = int(callback_data.split("_")[-1])
            context.user_data["delete_page"] = page
            await delete_command(update, context)

        # Подтверждение удаления
        elif callback_data.startswith("delete_confirm_"):
            subscription_id = int(callback_data.split("_")[-1])
            await confirm_delete(update, context, subscription_id)

        # Выполнить удаление
        elif callback_data.startswith("delete_yes_"):
            subscription_id = int(callback_data.split("_")[-1])
            await execute_delete(update, context, subscription_id)
            context.user_data["cached_subscriptions"] = None
            await asyncio.sleep(2)
            await query.edit_message_text(
                "🏠 Главное меню\n\nВыберите действие:",
                reply_markup=get_main_menu_keyboard(),
            )

        # No-op (для отображения номера страницы)
        elif callback_data == "noop":
            pass

        else:
            logger.warning("unknown_callback", callback_data=callback_data)
            await query.answer("Неизвестная команда", show_alert=True)

    except Exception as e:
        logger.error(
            "callback_handler_failed",
            callback_data=callback_data,
            error=str(e),
        )
        with contextlib.suppress(Exception):
            await query.edit_message_text("Произошла ошибка. Попробуйте позже.")
