import contextlib
from datetime import UTC, datetime

from telegram import LinkPreviewOptions, Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.subscriptions import (
    get_archived_subscriptions_keyboard,
    get_empty_archived_keyboard,
    get_empty_subscriptions_keyboard,
    get_subscriptions_list_keyboard,
)
from app.bot.utils.safe_edit import is_stale_callback_error
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

SUBSCRIPTIONS_PER_PAGE = 5


async def list_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик команды /list или callback "menu_list"

    Показывает список подписок пользователя с пагинацией.
    """
    if not update.effective_user:
        logger.error("list_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        elif update.message:
            await update.message.reply_text(
                "Ошибка: не удалось получить информацию о пользователе."
            )
        return

    chat_id = update.effective_user.id
    page = context.user_data.get("list_page", 0)
    logger.info("list_command", chat_id=chat_id, page=page)

    try:
        user_id = context.user_data.get("user_id")
        is_refresh = context.user_data.get("is_refresh", False)
        context.user_data["is_refresh"] = False

        async with HTTPClient() as client:
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id
                logger.info("user_id_cached", user_id=user_id)

            cached_subs = context.user_data.get("cached_subscriptions")
            if cached_subs and not is_refresh:
                subscriptions = cached_subs
                logger.info("subscriptions_from_cache", count=len(subscriptions))
            else:
                subscriptions = await client.get_user_subscriptions(user_id)
                context.user_data["cached_subscriptions"] = subscriptions
                logger.info(
                    "subscriptions_fetched", user_id=user_id, count=len(subscriptions)
                )

        if not subscriptions:
            message = (
                "📋 У вас пока нет подписок.\n\n"
                'Нажмите "➕ Добавить подписку", чтобы добавить подписку на товар.'
            )
            keyboard = get_empty_subscriptions_keyboard()
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message, reply_markup=keyboard
                )
            elif update.message:
                await update.message.reply_text(message, reply_markup=keyboard)
            return

        total_pages = (
            len(subscriptions) + SUBSCRIPTIONS_PER_PAGE - 1
        ) // SUBSCRIPTIONS_PER_PAGE
        page = min(page, total_pages - 1)
        start_idx = page * SUBSCRIPTIONS_PER_PAGE
        end_idx = start_idx + SUBSCRIPTIONS_PER_PAGE
        page_subscriptions = subscriptions[start_idx:end_idx]
        message = f"📋 Ваши подписки ({len(subscriptions)} шт.)\n\n"
        message += f"Страница {page + 1} из {total_pages}\n\n"

        for idx, sub in enumerate(page_subscriptions, start_idx + 1):
            raw_name = sub.get("product_name")
            consecutive_errors = sub.get("consecutive_errors", 0)
            current_price = sub.get("current_price")
            target_price = sub.get("target_price")
            marketplace = sub.get("marketplace", "").upper()
            alert_sent = sub.get("alert_sent", False)
            product_url = sub.get("product_url", "")
            cooldown_hours = sub.get("cooldown_hours", 24)

            display_name = raw_name if raw_name else "Товар (данные не получены)"
            message += f"{idx}. {display_name}\n"

            if marketplace:
                message += f"  🏪 {marketplace}\n"

            if current_price is not None:
                message += f"  💰 {float(current_price):,.2f} ₽\n"
            else:
                message += "  💰 Цена не определена\n"

            if target_price is not None:
                message += f"  🎯 {float(target_price):,.2f} ₽\n"

            message += f"  🔁 Уведомления: каждые {cooldown_hours}ч\n"

            if consecutive_errors > 0:
                max_errors = settings.max_consecutive_errors
                message += (
                    f"  📊 ⚠️Ошибка получения данных ({consecutive_errors}/"
                    f"{max_errors})\n"
                )
            elif alert_sent:
                message += "  📊 ✅ Уведомление отправлено\n"
            elif (
                target_price is not None
                and current_price is not None
                and float(current_price) <= float(target_price)
            ):
                message += "  📊 🔔 Цена достигла цели!\n"
            elif target_price is not None:
                message += "  📊 ⏳ Мониторинг\n"
            else:
                message += "  📊 ⏳ Мониторинг (без целевой цены)\n"

            # 3. Ссылка на товар
            if product_url:
                message += f"  🔗 {product_url}\n"

            message += "\n"

        message += f"\nОбновлено: {datetime.now(UTC).strftime('%H:%M:%S')}"
        keyboard = get_subscriptions_list_keyboard(
            page_subscriptions,
            page=page,
            total_pages=total_pages,
            action="view",
            show_refresh=True,
        )

        preview_options = LinkPreviewOptions(is_disabled=True)
        if update.callback_query:
            await update.callback_query.edit_message_text(
                message, reply_markup=keyboard, link_preview_options=preview_options
            )
        elif update.message:
            await update.message.reply_text(
                message, reply_markup=keyboard, link_preview_options=preview_options
            )

    except Exception as e:
        logger.error("list_command_failed", chat_id=chat_id, error=str(e))

        if is_stale_callback_error(e):
            return

        if update.callback_query:
            with contextlib.suppress(Exception):
                await update.callback_query.answer(
                    "⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True
                )


async def archived_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показывает список архивных подписок."""
    if not update.effective_user:
        return

    chat_id = update.effective_user.id
    logger.info("archived_command", chat_id=chat_id)

    try:
        async with HTTPClient() as client:
            user_id = context.user_data.get("user_id")
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            archived_subs = await client.get_archived_subscriptions(user_id)

            if not archived_subs:
                message = "🗄 У вас нет архивных подписок. Все ваши подписки активны!"
                keyboard = get_empty_archived_keyboard()
            else:
                message = f"🗄 Архивные подписки ({len(archived_subs)} шт.)\n\n"
                message += "Нажмите на подписку, чтобы реактивировать её:"
                keyboard = get_archived_subscriptions_keyboard(archived_subs)

            preview_options = LinkPreviewOptions(is_disabled=True)
            if update.callback_query:
                await update.callback_query.edit_message_text(
                    message, reply_markup=keyboard, link_preview_options=preview_options
                )
            elif update.message:
                await update.message.reply_text(
                    message, reply_markup=keyboard, link_preview_options=preview_options
                )

    except Exception as e:
        logger.error("archived_command_failed", chat_id=chat_id, error=str(e))
