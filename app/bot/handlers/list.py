import contextlib
from datetime import UTC, datetime

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.subscriptions import get_subscriptions_list_keyboard
from app.bot.utils.safe_edit import is_stale_callback_error
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

        logger.info("subscriptions_fetched", user_id=user_id, count=len(subscriptions))

        if not subscriptions:
            message = (
                "📋 У вас пока нет подписок.\n\n"
                'Нажмите "➕ Добавить товар", чтобы добавить подписку на товар.'
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            elif update.message:
                await update.message.reply_text(message)
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
            product_name = sub.get("product_name") or "Без названия"
            current_price = sub.get("current_price")
            target_price = sub.get("target_price")
            marketplace = sub.get("marketplace", "").upper()
            alert_sent = sub.get("alert_sent", False)
            message += f"{idx}. {product_name}\n"

            if marketplace:
                message += f"   🏪 {marketplace}\n"
            if current_price is not None:
                price_value = float(current_price)
                message += f"   💰 {price_value:,.2f} ₽\n"
            else:
                message += "   💰 Цена не определена\n"

            if target_price is not None:
                target_value = float(target_price)
                message += f"   🎯 {target_value:,.2f} ₽\n"

                if alert_sent:
                    message += "   📊 ✅ Уведомление отправлено\n"
                elif current_price is not None and current_price <= target_price:
                    message += "   📊 🔔 Цена достигла цели!\n"
                else:
                    message += "   📊 ⏳ Мониторинг\n"

            message += "\n"

        message += f"\nОбновлено: {datetime.now(UTC).strftime('%H:%M:%S')}"
        keyboard = get_subscriptions_list_keyboard(
            page_subscriptions,
            page=page,
            total_pages=total_pages,
            action="view",
            show_refresh=True,
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message, reply_markup=keyboard
            )
        elif update.message:
            await update.message.reply_text(message, reply_markup=keyboard)

    except Exception as e:
        logger.error("list_command_failed", chat_id=chat_id, error=str(e))

        if is_stale_callback_error(e):
            return

        if update.callback_query:
            with contextlib.suppress(Exception):
                await update.callback_query.answer(
                    "⚠️ Произошла ошибка. Попробуйте ещё раз.", show_alert=True
                )
