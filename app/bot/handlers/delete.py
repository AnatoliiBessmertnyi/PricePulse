from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.keyboards.subscriptions import (
    get_delete_confirmation_keyboard,
    get_subscriptions_list_keyboard,
)
from app.core.logging import get_logger

logger = get_logger(__name__)

# Количество подписок на странице
SUBSCRIPTIONS_PER_PAGE = 5


async def delete_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик callback "menu_delete"

    Показывает список подписок с кнопками удаления.
    """
    if not update.effective_user:
        logger.error("delete_no_user", update=update)
        if update.callback_query:
            await update.callback_query.answer("Ошибка: нет пользователя")
        return

    chat_id = update.effective_user.id
    page = context.user_data.get("delete_page", 0)

    logger.info(
        "delete_command",
        chat_id=chat_id,
        page=page,
    )

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

            subscriptions = await client.get_user_subscriptions(user_id)

        logger.info(
            "subscriptions_for_delete_fetched",
            user_id=user_id,
            count=len(subscriptions),
        )

        if not subscriptions:
            message = (
                "❌ У вас нет подписок для удаления.\n\n"
                'Нажмите "➕ Добавить подписку", чтобы добавить подписку.'
            )
            if update.callback_query:
                await update.callback_query.edit_message_text(message)
            return

        # Пагинация
        total_pages = (
            len(subscriptions) + SUBSCRIPTIONS_PER_PAGE - 1
        ) // SUBSCRIPTIONS_PER_PAGE
        page = min(page, total_pages - 1)
        start_idx = page * SUBSCRIPTIONS_PER_PAGE
        end_idx = start_idx + SUBSCRIPTIONS_PER_PAGE
        page_subscriptions = subscriptions[start_idx:end_idx]

        # Формируем текст
        message = "❌ Выберите подписку для удаления\n\n"
        message += f"Всего подписок: {len(subscriptions)}\n"
        message += f"Страница {page + 1} из {total_pages}\n\n"
        message += "Нажмите на товар, который хотите удалить:"

        keyboard = get_subscriptions_list_keyboard(
            page_subscriptions,
            page=page,
            total_pages=total_pages,
            action="delete",
        )

        if update.callback_query:
            await update.callback_query.edit_message_text(
                message, reply_markup=keyboard
            )

    except Exception as e:
        logger.error("delete_command_failed", chat_id=chat_id, error=str(e))
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "Произошла ошибка при получении списка подписок."
            )


async def confirm_delete(
    update: Update, context: ContextTypes.DEFAULT_TYPE, subscription_id: int
) -> None:
    """
    Запрос подтверждения удаления подписки

    Args:
        update: Update объект
        context: Context объект
        subscription_id: ID подписки для удаления
    """
    if not update.callback_query or not update.effective_user:
        return

    chat_id = update.effective_user.id
    logger.info("confirm_delete", chat_id=chat_id, subscription_id=subscription_id)

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

            subscriptions = await client.get_user_subscriptions(user_id)

        for sub in subscriptions:
            if sub.get("id") == subscription_id:
                subscription = sub
                break

        if not subscription:
            await update.callback_query.edit_message_text(
                "❌ Подписка не найдена или уже удалена."
            )
            return

        product_name = subscription.get("product_name") or "Без названия"
        current_price = subscription.get("current_price")
        message = "⚠️ Подтверждение удаления\n\n"
        message += "Вы действительно хотите удалить подписку?\n\n"
        message += f"📦 Товар: {product_name}\n"
        if current_price is not None:
            price_value = float(current_price)
            message += f"💰 Текущая цена: {price_value:,.2f} ₽\n"

        message += "\nЭто действие нельзя отменить."
        keyboard = get_delete_confirmation_keyboard(subscription_id)
        await update.callback_query.edit_message_text(message, reply_markup=keyboard)

    except Exception as e:
        logger.error(
            "confirm_delete_failed",
            chat_id=chat_id,
            subscription_id=subscription_id,
            error=str(e),
        )
        await update.callback_query.edit_message_text(
            "Произошла ошибка. Попробуйте позже."
        )


async def execute_delete(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    subscription_id: int,
) -> None:
    """
    Выполнить удаление подписки

    Args:
        update: Update объект
        context: Context объект
        subscription_id: ID подписки для удаления
    """
    if not update.callback_query or not update.effective_user:
        return

    chat_id = update.effective_user.id
    logger.info("execute_delete", chat_id=chat_id, subscription_id=subscription_id)

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

            success = await client.delete_subscription(
                subscription_id=subscription_id, user_id=user_id
            )

        if success:
            await update.callback_query.edit_message_text(
                "✅ Подписка успешно удалена!\n\n"
                'Нажмите "📋 Мои подписки", чтобы увидеть обновлённый список.'
            )
        else:
            await update.callback_query.edit_message_text(
                "❌ Подписка не найдена или уже удалена."
            )

    except Exception as e:
        logger.error(
            "execute_delete_failed",
            chat_id=chat_id,
            subscription_id=subscription_id,
            error=str(e),
        )
        await update.callback_query.edit_message_text(
            "Произошла ошибка при удалении. Попробуйте позже."
        )
