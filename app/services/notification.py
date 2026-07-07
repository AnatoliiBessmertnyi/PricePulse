import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.subscription import Subscription

logger = get_logger(__name__)


class NotificationService:
    def __init__(self) -> None:
        self._token = settings.telegram_bot_token
        base = settings.telegram_api_url or "https://api.telegram.org"
        self._base_url = base.rstrip("/")
        logger.info(
            "notification_service_initialized",
            telegram_api_url=settings.telegram_api_url,
            base_url=self._base_url,
            token_set=bool(self._token),
        )

    def notify_price_drop(self, subscription: Subscription) -> None:
        if not self._token:
            logger.warning("notification_skipped", reason="telegram_bot_token_not_set")
            return

        chat_id = subscription.user.chat_id
        text = (
            f"🔔 Цена снизилась!\n\n"
            f"📦 {subscription.product_name or 'Товар'}\n"
            f"💰 Новая цена: {subscription.current_price} ₽\n"
            f"🎯 Ваша цель: {subscription.target_price} ₽\n\n"
            f"🔗 {subscription.product_url}"
        )
        url = f"{self._base_url}/bot{self._token}/sendMessage"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(url, json={"chat_id": chat_id, "text": text})
                response.raise_for_status()

            logger.info("price_drop_notification_sent", subscription_id=subscription.id)
        except Exception as e:
            logger.error(
                "price_drop_notification_failed",
                subscription_id=subscription.id,
                chat_id=chat_id,
                error=str(e),
                error_type=type(e).__name__,
            )
