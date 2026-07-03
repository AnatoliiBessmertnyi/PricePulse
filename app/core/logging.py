import logging
import sys

import structlog


def _truncate_long_fields(_logger, _method_name, event_dict):
    """
    Обрезать длинные строковые поля в логах.

    Предотвращает вывод огромных HTML-страниц в логи.
    """
    max_length = 500

    for key, value in list(event_dict.items()):
        if isinstance(value, str) and len(value) > max_length:
            event_dict[key] = (
                value[:max_length] + f"... [truncated, original length: {len(value)}]"
            )

    return event_dict


def setup_logging(log_level: str = "INFO") -> None:
    """
    Настройка централизованного логирования для всего проекта.

    Args:
        log_level: Уровень логирования (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S", utc=False),
            _truncate_long_fields,
            structlog.dev.ConsoleRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, log_level)
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=False,
    )

    logging.basicConfig(
        format="%(message)s", stream=sys.stdout, level=getattr(logging, log_level)
    )
    sqlalchemy_logger = logging.getLogger("sqlalchemy.engine")
    sqlalchemy_logger.handlers.clear()
    sqlalchemy_logger.propagate = False

    for logger_name in ["sqlalchemy", "sqlalchemy.engine.Engine"]:
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = False

    logging.getLogger("uvicorn").handlers.clear()
    logging.getLogger("uvicorn.access").handlers.clear()
    logging.getLogger("uvicorn.error").handlers.clear()
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("aiogram").setLevel(logging.INFO)
    logging.getLogger("aio_pika").setLevel(logging.WARNING)
    logging.getLogger("celery").setLevel(logging.INFO)
    logging.getLogger("kombu").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)
    logging.getLogger("asyncpg").setLevel(logging.WARNING)

    if log_level == "DEBUG":
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Получить настроенный logger.

    Args:
        name: Имя logger (обычно __name__ модуля)

    Returns:
        Настроенный structlog logger
    """
    return structlog.get_logger(name)
