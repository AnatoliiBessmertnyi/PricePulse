from telegram.error import NetworkError, TimedOut

from app.core.logging import get_logger

logger = get_logger(__name__)


def is_stale_callback_error(error: Exception) -> bool:
    """
    Проверить, является ли ошибка связанной с устаревшим callback.

    Args:
        error: Исключение для проверки

    Returns:
        True если это ошибка устаревшего callback
    """
    error_msg = str(error)[:500].lower()
    return any(
        phrase in error_msg
        for phrase in [
            "query is too old",
            "message is not modified",
            "query id is invalid",
            "response timeout expired",
        ]
    )


def is_network_error(error: Exception) -> bool:
    """
    Проверить, является ли ошибка сетевой.

    Args:
        error: Исключение для проверки

    Returns:
        True если это сетевая ошибка
    """
    return (
        isinstance(error, (NetworkError, TimedOut)) or "network" in str(error).lower()
    )
