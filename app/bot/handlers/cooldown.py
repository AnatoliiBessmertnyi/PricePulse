from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from app.bot.client import HTTPClient
from app.bot.keyboards.subscriptions import get_cooldown_subscription_keyboard
from app.bot.states import WAITING_COOLDOWN_HOURS
from app.core.logging import get_logger

logger = get_logger(__name__)


async def start_cooldown_menu(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Точка входа: показать первую страницу подписок для настройки."""
    if not update.effective_user or not update.callback_query:
        return ConversationHandler.END

    chat_id = update.effective_user.id
    logger.info("start_cooldown_menu", chat_id=chat_id)

    try:
        async with HTTPClient() as client:
            user_id = context.user_data.get("user_id")
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            subscriptions = await client.get_user_subscriptions(user_id)
            context.user_data["cached_subscriptions"] = subscriptions

            if not subscriptions:
                await update.callback_query.answer(
                    "У вас нет активных подписок", show_alert=True
                )
                return ConversationHandler.END

            total_pages = (len(subscriptions) + 4) // 5
            page_subs = subscriptions[:5]

            keyboard = get_cooldown_subscription_keyboard(
                page_subs, page=0, total_pages=total_pages
            )
            await update.callback_query.edit_message_text(
                "Выберите подписку для настройки интервала уведомлений:",
                reply_markup=keyboard,
            )
            return WAITING_COOLDOWN_HOURS

    except Exception as e:
        logger.error("start_cooldown_menu_failed", chat_id=chat_id, error=str(e))
        await update.callback_query.answer(
            "⚠️ Ошибка. Попробуйте ещё раз.", show_alert=True
        )
        return ConversationHandler.END


async def handle_cooldown_pagination(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обработка переключения страниц внутри диалога настройки."""
    query = update.callback_query
    if not query or not query.data.startswith("page_set_cooldown_"):
        return WAITING_COOLDOWN_HOURS

    await query.answer()
    page = int(query.data.split("_")[-1])
    subscriptions = context.user_data.get("cached_subscriptions", [])

    if not subscriptions:
        return ConversationHandler.END

    total_pages = (len(subscriptions) + 4) // 5
    start_idx = page * 5
    end_idx = start_idx + 5
    page_subs = subscriptions[start_idx:end_idx]

    keyboard = get_cooldown_subscription_keyboard(
        page_subs, page=page, total_pages=total_pages
    )
    await query.edit_message_text(
        "Выберите подписку для настройки интервала уведомлений:", reply_markup=keyboard
    )
    return WAITING_COOLDOWN_HOURS


async def select_cooldown_subscription(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обработка выбора конкретной подписки."""
    query = update.callback_query
    if not query or not query.data.startswith("set_cooldown_select_"):
        return WAITING_COOLDOWN_HOURS

    sub_id = int(query.data.split("_")[-1])
    context.user_data["target_cooldown_sub_id"] = sub_id

    subs = context.user_data.get("cached_subscriptions", [])
    sub = next((s for s in subs if s.get("id") == sub_id), None)
    sub_name = sub.get("product_name") if sub else "Товар"
    context.user_data["target_cooldown_sub_name"] = sub_name or "Товар"

    text_to_show = (
        "Введите интервал уведомлений в часах (целое число от 1 до 168) для:\n"
        f"*{sub_name}*"
    )

    # Редактируем сообщение и ПОЛУЧАЕМ объект сообщения, чтобы сохранить его ID
    msg = await query.edit_message_text(
        text_to_show,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_cooldown")]]
        ),
    )
    # Сохраняем ID сообщения бота для последующего редактирования
    context.user_data["cooldown_prompt_msg_id"] = msg.message_id

    return WAITING_COOLDOWN_HOURS


async def receive_cooldown_hours(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Получить ввод, удалить его и отредактировать сообщение бота."""
    if not update.effective_user or not update.message:
        return ConversationHandler.END

    chat_id = update.effective_user.id
    text = update.message.text.strip()
    subscription_id = context.user_data.get("target_cooldown_sub_id")
    sub_name = context.user_data.get("target_cooldown_sub_name", "подписки")
    prompt_msg_id = context.user_data.get("cooldown_prompt_msg_id")

    if not subscription_id:
        await update.message.reply_text(
            "⚠️ Произошла ошибка. Начните заново через меню."
        )
        return ConversationHandler.END

    try:
        await update.message.delete()
    except Exception as e:
        logger.warning("failed_to_delete_user_message", chat_id=chat_id, error=str(e))

    try:
        hours = int(text)
        if not (1 <= hours <= 168):
            raise ValueError("Out of range")

        user_id = context.user_data.get("user_id")
        async with HTTPClient() as client:
            await client.update_subscription_cooldown(subscription_id, user_id, hours)

        if prompt_msg_id:
            success_keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⏱ Настроить другую", callback_data="set_cooldown_menu"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ К списку подписок", callback_data="menu_list"
                        )
                    ],
                ]
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=prompt_msg_id,
                    text=(
                        f"✅ Интервал для *{sub_name}* успешно изменен "
                        f"на **{hours} ч.**"
                    ),
                    parse_mode="Markdown",
                    reply_markup=success_keyboard,
                )
            except Exception as e:
                logger.warning("failed_to_edit_prompt_message", error=str(e))

        context.user_data.pop("target_cooldown_sub_id", None)
        context.user_data.pop("target_cooldown_sub_name", None)
        context.user_data.pop("cooldown_prompt_msg_id", None)
        return ConversationHandler.END

    except ValueError:
        if prompt_msg_id:
            error_text = (
                f"⚠️ *Ошибка:* введено некорректное значение.\n\n"
                f"Введите интервал уведомлений в часах (целое число от 1 до 168) для:\n"
                f"*{sub_name}*"
            )
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=prompt_msg_id,
                    text=error_text,
                    parse_mode="Markdown",
                    reply_markup=InlineKeyboardMarkup(
                        [
                            [
                                InlineKeyboardButton(
                                    "❌ Отмена", callback_data="cancel_cooldown"
                                )
                            ]
                        ]
                    ),
                )
            except Exception as e:
                logger.warning("failed_to_edit_error_message", error=str(e))

        return WAITING_COOLDOWN_HOURS

    except Exception as e:
        logger.error("receive_cooldown_hours_failed", chat_id=chat_id, error=str(e))
        await context.bot.send_message(
            chat_id=chat_id,
            text="⚠️ Произошла непредвиденная ошибка. Попробуйте начать заново.",
        )
        return ConversationHandler.END


async def cancel_cooldown_setup(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Отменить настройку."""
    context.user_data.pop("target_cooldown_sub_id", None)
    context.user_data.pop("target_cooldown_sub_name", None)
    context.user_data.pop("cooldown_prompt_msg_id", None)

    if update.callback_query:
        await update.callback_query.edit_message_text("Настройка интервала отменена.")
    elif update.message:
        await update.message.reply_text("Настройка интервала отменена.")

    return ConversationHandler.END
