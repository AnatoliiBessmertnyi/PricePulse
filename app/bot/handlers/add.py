from telegram import Update
from telegram.ext import ContextTypes

from app.bot.client import HTTPClient
from app.bot.utils.url_parser import clean_and_validate_url
from app.core.logging import get_logger

logger = get_logger(__name__)


async def add_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """
    Обработчик команды /add <url>

    Добавляет подписку на товар.
    Поддерживает текст с URL (например, "Смотри что я нашел! https://ozon.ru/...")
    """
    if not update.effective_user:
        logger.error("add_no_user", update=update)
        await update.message.reply_text(
            "Ошибка: не удалось получить информацию о пользователе."
        )
        return

    chat_id = update.effective_user.id

    # Проверяем, что передан аргумент
    if not context.args or len(context.args) == 0:
        await update.message.reply_text(
            "Использование: /add <ссылка на товар>\n\n"
            "Пример:\n"
            "/add https://www.ozon.ru/product/smartfon-samsung-galaxy-a54-256gb/"
        )
        return

    # Объединяем все аргументы в один текст
    text = " ".join(context.args)

    logger.info(
        "add_command",
        chat_id=chat_id,
        text=text,
    )

    # Извлекаем и валидируем URL
    url, marketplace = clean_and_validate_url(text)

    if not url:
        await update.message.reply_text(
            "Не удалось найти корректную ссылку в сообщении.\n\n"
            "Убедитесь, что вы отправили ссылку на товар с поддерживаемого маркетплейса (ozon.ru)."
        )
        return

    if not marketplace:
        await update.message.reply_text(
            f"Маркетплейс не поддерживается.\n\n"
            f"Поддерживаемые маркетплейсы: Ozon (ozon.ru)\n\n"
            f"Отправленная ссылка: {url}"
        )
        return

    try:
        # Сначала регистрируем пользователя (если ещё не зарегистрирован)
        async with HTTPClient() as client:
            user_data = await client.create_user(
                chat_id=chat_id,
                username=update.effective_user.username,
            )
            user_id = user_data.get("id")

            # Создаём подписку
            subscription_data = await client.create_subscription(
                user_id=user_id,
                marketplace=marketplace,
                product_url=url,
            )

        subscription_id = subscription_data.get("id")
        product_name = subscription_data.get("product_name")
        current_price = subscription_data.get("current_price")

        logger.info(
            "subscription_created",
            subscription_id=subscription_id,
            user_id=user_id,
            product_url=url,
            marketplace=marketplace,
        )

        # Формируем ответ
        response = "✅ Подписка успешно добавлена!\n\n"
        if product_name:
            response += f"📦 Товар: {product_name}\n"
        response += f"🔗 Ссылка: {url}\n"
        if current_price is not None:
            response += f"💰 Цена: {current_price} ₽\n"
        response += "\nСистема будет проверять цену каждые 15 минут и уведомит вас при снижении."

        await update.message.reply_text(response)

    except Exception as e:
        logger.error(
            "add_command_failed",
            chat_id=chat_id,
            url=url,
            error=str(e),
        )

        # Обрабатываем специфичные ошибки
        error_message = str(e)
        if "400" in error_message:
            await update.message.reply_text(
                "Ошибка: некорректные данные. Проверьте ссылку и попробуйте снова."
            )
        elif "404" in error_message:
            await update.message.reply_text(
                "Ошибка: товар не найден. Проверьте ссылку."
            )
        elif "500" in error_message:
            await update.message.reply_text("Ошибка сервера. Попробуйте позже.")
        else:
            await update.message.reply_text(
                "Произошла ошибка при добавлении подписки. Попробуйте позже."
            )
