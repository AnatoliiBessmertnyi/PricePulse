import contextlib
from decimal import Decimal, InvalidOperation

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.main_menu import get_main_menu_keyboard
from app.bot.keyboards.subscriptions import (
    get_cancel_target_keyboard,
    get_notification_target_cancel_keyboard,
    get_price_drop_keyboard,
    get_target_subscription_keyboard,
)
from app.bot.states import WAITING_FOR_TARGET_PRICE
from app.bot.utils.safe_edit import is_stale_callback_error
from app.core.logging import get_logger

logger = get_logger(__name__)

SUBSCRIPTIONS_PER_PAGE = 5


async def _render_target_menu(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    request_message_id: int | None,
    update: Update | None = None,
) -> None:
    """Отрендерить меню выбора подписки для установки target_price."""
    user_id = context.user_data.get("user_id")
    if not user_id:
        return

    async with HTTPClient() as client:
        subscriptions = await client.get_user_subscriptions(user_id)

    if not subscriptions:
        return

    total_pages = (
        len(subscriptions) + SUBSCRIPTIONS_PER_PAGE - 1
    ) // SUBSCRIPTIONS_PER_PAGE
    page = context.user_data.get("set_target_page", 0)
    page = min(page, total_pages - 1)
    start_idx = page * SUBSCRIPTIONS_PER_PAGE
    end_idx = start_idx + SUBSCRIPTIONS_PER_PAGE
    page_subscriptions = subscriptions[start_idx:end_idx]
    menu_message = "🎯 Выберите подписку для установки целевой цены\n\n"
    menu_message += f"Всего подписок: {len(subscriptions)}\n"
    menu_message += f"Страница {page + 1} из {total_pages}"
    keyboard = get_target_subscription_keyboard(
        page_subscriptions, page=page, total_pages=total_pages
    )
    if request_message_id:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=request_message_id,
            text=menu_message,
            reply_markup=keyboard,
        )
    elif update and update.callback_query:
        await update.callback_query.edit_message_text(
            menu_message, reply_markup=keyboard
        )


async def set_target_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список подписок для выбора при установке target_price."""
    context.user_data.pop("new_subscription_id", None)
    if not update.effective_user:
        logger.error("set_target_menu_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        return

    chat_id = update.effective_user.id
    page = context.user_data.get("set_target_page", 0)
    logger.info("set_target_menu", chat_id=chat_id, page=page)

    try:
        user_id = context.user_data.get("user_id")
        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            subscriptions = await client.get_user_subscriptions(user_id)

        logger.info(
            "subscriptions_for_target_fetched",
            user_id=user_id,
            count=len(subscriptions),
        )

        if not subscriptions:
            message = (
                "❌ У вас нет подписок.\n\nНажмите '➕ Добавить подписку', чтобы "
                "добавить подписку."
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message, reply_markup=get_main_menu_keyboard()
                )
            elif update.message:
                await update.message.reply_text(
                    message, reply_markup=get_main_menu_keyboard()
                )
            return

        total_pages = (
            len(subscriptions) + SUBSCRIPTIONS_PER_PAGE - 1
        ) // SUBSCRIPTIONS_PER_PAGE
        page = min(page, total_pages - 1)
        start_idx = page * SUBSCRIPTIONS_PER_PAGE
        end_idx = start_idx + SUBSCRIPTIONS_PER_PAGE
        page_subscriptions = subscriptions[start_idx:end_idx]

        message = "🎯 Выберите подписку для установки целевой цены\n\n"
        message += f"Всего подписок: {len(subscriptions)}\n"
        message += f"Страница {page + 1} из {total_pages}"

        keyboard = get_target_subscription_keyboard(
            page_subscriptions, page=page, total_pages=total_pages
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message, reply_markup=keyboard
            )
        elif update.message:
            await update.message.reply_text(message, reply_markup=keyboard)

    except Exception as e:
        logger.error("set_target_menu_failed", chat_id=chat_id, error=str(e))
        if is_stale_callback_error(e):
            logger.warning("stale_callback_ignored", chat_id=chat_id)
            return
        if update.callback_query:
            with contextlib.suppress(Exception):
                await update.callback_query.answer(
                    "⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True
                )


async def start_change_target_from_notification(
    update: Update, context: ContextTypes.DEFAULT_TYPE, subscription_id: int
) -> int:
    """Обработчик нажатия 'Изменить цель' прямо из уведомления."""
    query = update.callback_query
    if not query or not query.from_user:
        return -1

    chat_id = query.from_user.id
    user_id = context.user_data.get("user_id")

    try:
        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=query.from_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            subs = await client.get_user_subscriptions(user_id)
            sub = next((s for s in subs if s.get("id") == subscription_id), None)

            if not sub:
                await query.answer(
                    "⚠️ Эта подписка не найдена или уже в архиве", show_alert=True
                )
                return -1

            context.user_data["target_subscription_id"] = subscription_id
            context.user_data["from_notification"] = True
            context.user_data["target_request_message_id"] = query.message.message_id

            product_name = sub.get("product_name") or "Без названия"
            current_price = sub.get("current_price")
            target_price = sub.get("target_price")

            msg = f"🎯 Установка новой целевой цены\n\n📦 Товар: {product_name}\n"
            if current_price is not None:
                msg += f"💰 Текущая цена: {float(current_price):,.0f} ₽\n"
            if target_price is not None:
                msg += f"🎯 Текущая цель: {float(target_price):,.0f} ₽\n"
            msg += "\nОтправьте новую целевую цену в рублях (например: 1500):"

            await query.edit_message_text(
                msg,
                reply_markup=get_notification_target_cancel_keyboard(subscription_id),
            )
            return WAITING_FOR_TARGET_PRICE

    except Exception as e:
        logger.error(
            "change_target_from_notification_failed", error=str(e), exc_info=True
        )
        await query.answer("⚠️ Произошла ошибка при загрузке данных", show_alert=True)
        return -1


async def set_target_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработчик выбора подписки для установки target_price из обычного меню."""
    if not update.effective_user:
        logger.error("set_target_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        return -1

    chat_id = update.effective_user.id
    query = update.callback_query

    if not query:
        return -1

    callback_data = query.data
    if not callback_data.startswith(("set_target_select_", "set_target_new_")):
        return -1

    subscription_id = int(callback_data.split("_")[-1])
    context.user_data["target_subscription_id"] = subscription_id
    context.user_data["from_notification"] = False

    logger.info("set_target_start", chat_id=chat_id, subscription_id=subscription_id)

    try:
        user_id = context.user_data.get("user_id")
        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            subscriptions = await client.get_user_subscriptions(user_id)

        subscription = None
        for sub in subscriptions:
            if sub.get("id") == subscription_id:
                subscription = sub
                break

        if not subscription:
            await query.edit_message_text(
                "❌ Подписка не найдена.", reply_markup=get_main_menu_keyboard()
            )
            return -1

        product_name = subscription.get("product_name") or "Без названия"
        current_price = subscription.get("current_price")
        target_price = subscription.get("target_price")

        message = "🎯 Установка целевой цены\n\n"
        message += f"📦 Товар: {product_name}\n"

        if current_price is not None:
            message += f"💰 Текущая цена: {float(current_price):,.2f} ₽\n"
        if target_price is not None:
            message += f"🎯 Текущая цель: {float(target_price):,.2f} ₽\n"

        message += "\nОтправьте новую целевую цену в рублях.\n\n"
        message += "Примеры:\n• 1000\n• 1500.50\n\nДля отмены нажмите кнопку ниже:"

        await query.edit_message_text(
            message, reply_markup=get_cancel_target_keyboard()
        )
        context.user_data["target_request_message_id"] = query.message.message_id
        return WAITING_FOR_TARGET_PRICE

    except Exception as e:
        logger.error("set_target_command_failed", chat_id=chat_id, error=str(e))
        await query.edit_message_text(
            "Произошла ошибка. Попробуйте позже.", reply_markup=get_main_menu_keyboard()
        )
        return -1


async def handle_target_price(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> int:
    """Обработчик получения target_price от пользователя."""
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

    try:
        target_price = Decimal(text.replace(",", "."))
        if target_price <= 0:
            raise ValueError("Цена должна быть положительной")
    except (InvalidOperation, ValueError) as e:
        logger.warning("invalid_target_price", chat_id=chat_id, text=text, error=str(e))
        await update.message.reply_text(
            "❌ Некорректная цена. Пожалуйста, отправьте число.\n\nПримеры:\n• 1000\n• "
            "1500.50\n\nДля отмены нажмите кнопку ниже:",
            reply_markup=get_cancel_target_keyboard(),
        )
        return WAITING_FOR_TARGET_PRICE

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
        context.user_data["cached_subscriptions"] = None

        with contextlib.suppress(Exception):
            await update.message.delete()

        if context.user_data.get("from_notification"):
            request_message_id = context.user_data.get("target_request_message_id")
            if request_message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=request_message_id,
                    text=(
                        f"✅ Целевая цена успешно обновлена на "
                        f"**{float(target_price):,.0f} ₽**!\n\n"
                        f"Мы сообщим вам, когда цена опустится ниже этого значения."
                    ),
                    parse_mode="Markdown",
                    reply_markup=get_price_drop_keyboard(subscription_id),
                )

            context.user_data.pop("from_notification", None)
            context.user_data.pop("target_request_message_id", None)
            context.user_data.pop("target_subscription_id", None)
            return -1

        request_message_id = context.user_data.get("target_request_message_id")
        new_subscription_id = context.user_data.get("new_subscription_id")
        if new_subscription_id == subscription_id:
            if request_message_id:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=request_message_id,
                    text=(
                        f"✅ Целевая цена успешно обновлена на "
                        f"**{float(target_price):,.0f} ₽**!\n\n"
                        f"Мониторинг продолжится с новыми параметрами."
                    ),
                    parse_mode="Markdown",
                    reply_markup=get_main_menu_keyboard(),
                )
            context.user_data.pop("new_subscription_id", None)
        else:
            await _render_target_menu(context, chat_id, request_message_id)

        context.user_data.pop("target_request_message_id", None)
        return -1

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
            reply_markup=get_cancel_target_keyboard(),
        )
        return WAITING_FOR_TARGET_PRICE


async def cancel_set_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Отмена установки target_price - возврат в меню выбора подписки."""
    chat_id = update.effective_user.id if update.effective_user else None
    request_message_id = context.user_data.get("target_request_message_id")

    if context.user_data.get("from_notification"):
        if request_message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=request_message_id,
                text="❌ Изменение целевой цены отменено.",
                reply_markup=None,
            )
        context.user_data.pop("from_notification", None)
        context.user_data.pop("target_request_message_id", None)
        context.user_data.pop("target_subscription_id", None)
        return -1

    await _render_target_menu(context, chat_id, request_message_id, update)
    context.user_data.pop("target_request_message_id", None)
    logger.info("cancel_set_target", chat_id=chat_id)
    return -1
