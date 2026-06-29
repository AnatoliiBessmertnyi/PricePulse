import structlog
from decimal import Decimal
from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient

logger = structlog.get_logger()


async def list_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик команды /list
    
    Показывает список подписок пользователя.
    """
    if not update.effective_user:
        logger.error("list_no_user", update=update)
        await update.message.reply_text(
            "Ошибка: не удалось получить информацию о пользователе."
        )
        return

    chat_id = update.effective_user.id

    logger.info(
        "list_command",
        chat_id=chat_id,
    )

    try:
        async with HTTPClient() as client:
            # Сначала получаем пользователя
            user_data = await client.create_user(
                chat_id=chat_id,
                username=update.effective_user.username,
            )
            user_id = user_data.get("id")

            # Получаем список подписок
            subscriptions = await client.get_user_subscriptions(user_id)

        logger.info(
            "subscriptions_fetched",
            user_id=user_id,
            count=len(subscriptions),
        )

        if not subscriptions:
            await update.message.reply_text(
                "У вас пока нет подписок.\n\n"
                "Используйте команду /add <ссылка>, чтобы добавить подписку на товар."
            )
            return

        # Формируем список подписок
        response = f"📋 Ваши подписки ({len(subscriptions)}):\n\n"

        for idx, sub in enumerate(subscriptions, 1):
            product_name = sub.get("product_name") or "Без названия"
            product_url = sub.get("product_url")
            current_price = sub.get("current_price")
            marketplace = sub.get("marketplace", "").upper()
            is_active = sub.get("is_active", True)

            response += f"{idx}. {product_name}\n"
            if marketplace:
                response += f"   🏪 {marketplace}\n"
            if current_price is not None:
                # Форматируем цену
                price_value = float(current_price)
                response += f"   💰 {price_value:,.2f} ₽\n"
            else:
                response += f"   💰 Цена не определена\n"
            response += f"   🔗 {product_url}\n"
            
            if not is_active:
                response += f"   ⚠️ Неактивна\n"
            
            response += "\n"

        # Telegram имеет лимит на длину сообщения (4096 символов)
        # Разбиваем на несколько сообщений если нужно
        if len(response) > 4000:
            chunks = []
            current_chunk = f"📋 Ваши подписки ({len(subscriptions)}):\n\n"
            
            for idx, sub in enumerate(subscriptions, 1):
                product_name = sub.get("product_name") or "Без названия"
                product_url = sub.get("product_url")
                current_price = sub.get("current_price")
                marketplace = sub.get("marketplace", "").upper()
                is_active = sub.get("is_active", True)

                item = f"{idx}. {product_name}\n"
                if marketplace:
                    item += f"   🏪 {marketplace}\n"
                if current_price is not None:
                    price_value = float(current_price)
                    item += f"   💰 {price_value:,.2f} ₽\n"
                else:
                    item += f"   💰 Цена не определена\n"
                item += f"   🔗 {product_url}\n"
                
                if not is_active:
                    item += f"   ⚠️ Неактивна\n"
                
                item += "\n"

                if len(current_chunk) + len(item) > 4000:
                    chunks.append(current_chunk)
                    current_chunk = item
                else:
                    current_chunk += item
            
            if current_chunk:
                chunks.append(current_chunk)

            for chunk in chunks:
                await update.message.reply_text(chunk)
        else:
            await update.message.reply_text(response)

    except Exception as e:
        logger.error(
            "list_command_failed",
            chat_id=chat_id,
            error=str(e),
        )
        await update.message.reply_text(
            "Произошла ошибка при получении списка подписок. Попробуйте позже."
        )
