from app.core.logging import get_logger
from app.models.subscription import Subscription

logger = get_logger(__name__)


class NotificationService:
    """Сервис для отправки уведомлений пользователям."""

    async def notify_price_drop(self, subscription: Subscription) -> None:
        """
        Уведомить пользователя о снижении цены до target_price.

        В будущем здесь будет интеграция с Telegram Bot.
        """
        logger.info(
            "price_drop_alert",
            subscription_id=subscription.id,
            user_id=subscription.user_id,
            current_price=str(subscription.current_price),
            target_price=str(subscription.target_price),
            product_name=subscription.product_name,
        )
        # TODO: Интеграция с Telegram Bot (Sprint 2, шаг 2)
