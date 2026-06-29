import signal
import sys

import structlog
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

from app.bot.config import bot_settings
from app.bot.handlers.start import start_command
from app.bot.handlers.add import add_command
from app.bot.handlers.list import list_command

logger = structlog.get_logger()


def setup_logging():
    """Настройка structlog для бота"""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


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
    setup_logging()

    if not bot_settings.telegram_bot_token:
        logger.error("telegram_bot_token_not_set")
        sys.exit(1)

    logger.info("starting_bot")

    # Создаём приложение бота с увеличенными timeout
    application = (
        Application.builder()
        .token(bot_settings.telegram_bot_token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("add", add_command))
    application.add_handler(CommandHandler("list", list_command))

    # Регистрируем глобальный обработчик ошибок
    application.add_error_handler(error_handler)

    # Обработка graceful shutdown
    def shutdown_handler(signum, frame):
        logger.info("shutdown_signal_received", signum=signum)
        application.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    # Запускаем бота
    logger.info("bot_started")
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )
    logger.info("bot_stopped")


if __name__ == "__main__":
    main()
