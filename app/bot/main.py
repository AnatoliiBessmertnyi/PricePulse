import signal
import sys

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

from app.bot.config import bot_settings
from app.bot.handlers.add import add_command, cancel_add, handle_url
from app.bot.handlers.callbacks import button_handler
from app.bot.handlers.help import help_command
from app.bot.handlers.list import list_command
from app.bot.handlers.start import start_command
from app.bot.states import WAITING_FOR_URL
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

logger = get_logger(__name__)


async def error_handler(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Глобальный обработчик ошибок"""
    logger.error(
        "telegram_error",
        exception=str(context.error),
        error_type=type(context.error).__name__,
        update=update,
    )

    if isinstance(update, Update) and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Произошла непредвиденная ошибка. Попробуйте позже."
            )
        except Exception as send_error:
            logger.error(
                "error_handler_send_failed",
                error=str(send_error),
            )


def main():
    """Точка входа для запуска бота"""
    setup_logging(settings.log_level)

    if not bot_settings.telegram_bot_token:
        logger.error("telegram_bot_token_not_set")
        sys.exit(1)

    logger.info("starting_bot")

    if bot_settings.telegram_api_url:
        # Используем Cloudflare Worker как кастомный Telegram API URL
        logger.info("using_custom_api_url", url=bot_settings.telegram_api_url)
        api_url = bot_settings.telegram_api_url.rstrip("/")

        # Создаём HTTPXRequest с таймаутами
        request = HTTPXRequest(
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0,
        )

        # Создаём Bot объект с плейсхолдером {token}
        bot = Bot(
            token=bot_settings.telegram_bot_token,
            base_url=api_url + "/bot{token}",
            base_file_url=api_url + "/file/bot{token}",
            request=request,
        )
        application = Application.builder().bot(bot).build()
    else:
        # Стандартный режим без кастомного API URL
        application = (
            Application.builder()
            .token(bot_settings.telegram_bot_token)
            .connect_timeout(30.0)
            .read_timeout(30.0)
            .write_timeout(30.0)
            .pool_timeout(30.0)
            .build()
        )

    # ConversationHandler для добавления подписки
    add_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("add", add_command),
            CallbackQueryHandler(add_command, pattern="^menu_add$"),
        ],
        states={
            WAITING_FOR_URL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url)
            ],
        },
        fallbacks=[
            CallbackQueryHandler(cancel_add, pattern="^cancel_add$"),
        ],
        name="add_conversation",
        persistent=False,
    )

    # Регистрируем handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("list", list_command))
    application.add_handler(add_conversation_handler)

    # Callback query handler для всех inline кнопок
    application.add_handler(CallbackQueryHandler(button_handler))

    application.add_error_handler(error_handler)

    def shutdown_handler(signum, frame):
        logger.info("shutdown_signal_received", signum=signum)
        application.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    logger.info("bot_started")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
        poll_interval=1.0,
        timeout=5.0,
    )
    logger.info("bot_stopped")


if __name__ == "__main__":
    main()
