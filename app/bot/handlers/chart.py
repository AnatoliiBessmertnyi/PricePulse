import contextlib

from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.subscriptions import (
    get_chart_error_keyboard,
    get_chart_period_keyboard,
    get_chart_subscription_keyboard,
)
from app.core.logging import get_logger

logger = get_logger(__name__)


async def chart_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать список всех подписок (активных и архивных) для выбора графика."""
    if not update.effective_user or not update.callback_query:
        return

    query = update.callback_query
    await query.answer()
    chat_id = update.effective_user.id
    logger.info("chart_menu", chat_id=chat_id)

    try:
        async with HTTPClient() as client:
            user_id = context.user_data.get("user_id")
            if not user_id:
                user_data = await client.create_user(
                    chat_id=chat_id, username=update.effective_user.username
                )
                user_id = user_data.get("id")
                context.user_data["user_id"] = user_id

            active_subs = await client.get_user_subscriptions(user_id)
            archived_subs = await client.get_archived_subscriptions(user_id)

            for sub in archived_subs:
                name = sub.get("product_name") or "Без названия"
                sub["display_name"] = f"🗄 {name}"
            for sub in active_subs:
                sub["display_name"] = sub.get("product_name") or "Товар"

            all_subs = active_subs + archived_subs
            context.user_data["chart_cached_subscriptions"] = all_subs

            if not all_subs:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id, text="У вас нет подписок для просмотра графиков."
                )
                return

            total_pages = (len(all_subs) + 4) // 5
            page = context.user_data.get("chart_page", 0)
            start_idx = page * 5
            end_idx = start_idx + 5
            page_subs = all_subs[start_idx:end_idx]

            keyboard = get_chart_subscription_keyboard(
                page_subs, page=page, total_pages=total_pages
            )

            try:
                await query.edit_message_text(
                    "📊 Выберите подписку для просмотра графика:",
                    reply_markup=keyboard,
                )
            except Exception:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text="📊 Выберите подписку для просмотра графика:",
                    reply_markup=keyboard,
                )

    except Exception as e:
        logger.error("chart_menu_failed", chat_id=chat_id, error=str(e))
        await query.answer("⚠️ Ошибка. Попробуйте ещё раз.", show_alert=True)


async def show_chart(
    update: Update, context: ContextTypes.DEFAULT_TYPE, sub_id: int, period: str = "7d"
) -> None:
    """Делегирует генерацию и отправку графика API."""
    query = update.callback_query
    if not query:
        return

    await query.answer("⏳ Генерация графика...")
    chat_id = query.from_user.id
    logger.info("show_chart", chat_id=chat_id, sub_id=sub_id, period=period)
    context.user_data[f"chart_period_{sub_id}"] = period

    try:
        async with HTTPClient() as client:
            subs = context.user_data.get("chart_cached_subscriptions", [])
            sub = next((s for s in subs if s.get("id") == sub_id), None)
            if not sub:
                user_id = context.user_data.get("user_id")
                subs = await client.get_user_subscriptions(user_id)
                sub = next((s for s in subs if s.get("id") == sub_id), None)

            if not sub:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id, text="⚠️ Подписка не найдена."
                )
                return

            sub_name = sub.get("product_name") or "Товар"
            target_price = sub.get("target_price")
            user_id = context.user_data.get("user_id")
            caption = f"📊 *{sub_name}*\nПериод: {period}"
            if target_price:
                caption += f" | Цель: {float(target_price):,.0f} ₽"

            keyboard = get_chart_period_keyboard(sub_id, period)
            success = await client.send_chart_to_telegram(
                subscription_id=sub_id,
                user_id=user_id,
                chat_id=chat_id,
                period=period,
                caption=caption,
                reply_markup=keyboard.to_dict(),
            )

            if success:
                with contextlib.suppress(Exception):
                    await query.message.delete()
            else:
                await query.message.delete()
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=(
                        f"⚠️ Не удалось построить график для *{sub_name}* из-за ошибки "
                        "сети.\nПопробуйте еще раз или выберите другую подписку."
                    ),
                    parse_mode="Markdown",
                    reply_markup=get_chart_error_keyboard(sub_id),
                )

    except Exception as e:
        logger.error("show_chart_failed", chat_id=chat_id, sub_id=sub_id, error=str(e))
        await query.message.delete()
        await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⚠️ Произошла непредвиденная ошибка при построении графика для "
                f"*{sub_name}*."
            ),
            parse_mode="Markdown",
            reply_markup=get_chart_error_keyboard(sub_id),
        )


async def handle_chart_period_change(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Обработка нажатия на кнопки периода (7д, 30д, всё)."""
    query = update.callback_query
    if not query or not query.data.startswith("chart_period_"):
        return

    parts = query.data.split("_")
    sub_id = int(parts[2])
    period = parts[3]
    await show_chart(update, context, sub_id, period)
