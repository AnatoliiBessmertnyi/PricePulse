import asyncio
import contextlib

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.handlers.add import add_command
from app.bot.handlers.delete import confirm_delete, delete_command, execute_delete
from app.bot.handlers.help import help_command
from app.bot.handlers.list import archived_command, list_command
from app.bot.handlers.set_target import set_target_menu
from app.bot.keyboards.main_menu import get_main_menu_keyboard
from app.bot.utils.safe_edit import is_stale_callback_error
from app.core.logging import get_logger

logger = get_logger(__name__)


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
            context.user_data.pop("new_subscription_id", None)
            await query.edit_message_text(
                "🏠 Главное меню\n\nВыберите действие:",
                reply_markup=get_main_menu_keyboard(),
            )

        # Меню - Мои подписки
        elif callback_data == "menu_list":
            context.user_data["list_page"] = 0
            await list_command(update, context)

        # Меню - Добавить подписку
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

        # Меню установки target_price
        elif callback_data == "set_target_menu":
            context.user_data["set_target_page"] = 0
            await set_target_menu(update, context)

        # Пагинация списка выбора подписки для target
        elif callback_data.startswith("page_set_target_"):
            page = int(callback_data.split("_")[-1])
            context.user_data["set_target_page"] = page
            await set_target_menu(update, context)

        # Отмена установки target_price
        elif callback_data == "cancel_target":
            await set_target_menu(update, context)

        # Установка target_price (обрабатывается ConversationHandler)
        elif (
            callback_data.startswith("set_target_select_")
            or callback_data.startswith("set_target_new_")
            or callback_data == "noop"
        ):
            pass

        elif callback_data == "menu_archived":
            await archived_command(update, context)

        elif callback_data.startswith("reactivate_confirm_"):
            subscription_id = int(callback_data.split("_")[-1])
            await query.edit_message_text(
                "♻️ Реактивировать эту подписку?\n\n"
                "Счетчик ошибок будет сброшен, и мониторинг возобновится.",
                reply_markup=InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton(
                                "✅ Да, реактивировать",
                                callback_data=f"reactivate_yes_{subscription_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                "❌ Отмена", callback_data="menu_archived"
                            )
                        ],
                    ]
                ),
            )

        elif callback_data.startswith("reactivate_yes_"):
            subscription_id = int(callback_data.split("_")[-1])
            user_id = context.user_data.get("user_id")

            async with HTTPClient() as client:
                success = await client.reactivate_subscription(subscription_id, user_id)

            if success:
                context.user_data["cached_subscriptions"] = None
                await archived_command(update, context)
            else:
                await query.edit_message_text("⚠️ Не удалось реактивировать подписку.")

        else:
            logger.warning("unknown_callback", callback_data=callback_data)
            await query.answer("Неизвестная команда", show_alert=True)

    except Exception as e:
        logger.error(
            "callback_handler_failed", callback_data=callback_data, error=str(e)
        )
        if is_stale_callback_error(e):
            return

        with contextlib.suppress(Exception):
            await query.answer(
                "⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True
            )
