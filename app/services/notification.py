from datetime import UTC, datetime
from decimal import Decimal

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.models.subscription import Subscription
from app.services.subscription import SubscriptionService

logger = get_logger(__name__)


class NotificationService:
    def __init__(self, subscription_service: SubscriptionService | None = None) -> None:
        self._token = settings.telegram_bot_token
        self._subscription_service = subscription_service
        base = settings.telegram_api_url or "https://api.telegram.org"
        self._base_url = base.rstrip("/")

    def should_send_alert(
        self, subscription: Subscription, current_price: Decimal
    ) -> bool:
        """Проверить нужно ли отправлять уведомление."""
        if subscription.target_price is None:
            return False

        if current_price <= subscription.target_price:
            if not subscription.alert_sent:
                return True

            if subscription.last_alert_at:
                now = datetime.now(UTC)
                last_alert = subscription.last_alert_at
                if last_alert.tzinfo is None:
                    last_alert = last_alert.replace(tzinfo=UTC)
                hours_since_last = (now - last_alert).total_seconds() / 3600
                if hours_since_last >= subscription.cooldown_hours:
                    return True

            return False
        if subscription.alert_sent:
            subscription.alert_sent = False
        return False

    def notify_price_drop(self, subscription: Subscription) -> None:
        """Отправить уведомление о снижении цены."""
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
                response = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "link_preview_options": {"is_disabled": True},
                    },
                )
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

    def notify_subscription_archived(self, subscription: Subscription) -> None:
        """Отправить уведомление о том, что подписка архивирована из-за ошибок."""
        if not self._token:
            return

        chat_id = subscription.user.chat_id
        text = (
            f"🗄 Подписка архивирована\n\n"
            f"📦 {subscription.product_name or 'Товар'}\n"
            f"🔗 {subscription.product_url}\n\n"
            f"Не удалось получить данные о цене несколько раз подряд. "
            f"Возможно, товар удален или ссылка устарела.\n"
            f"Вы можете реактивировать её в разделе 'Архивные подписки'."
        )
        url = f"{self._base_url}/bot{self._token}/sendMessage"

        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.post(
                    url,
                    json={
                        "chat_id": chat_id,
                        "text": text,
                        "link_preview_options": {"is_disabled": True},
                    },
                )
                response.raise_for_status()
            logger.info("archive_notification_sent", subscription_id=subscription.id)
        except Exception as e:
            logger.error(
                "archive_notification_failed",
                subscription_id=subscription.id,
                error=str(e),
            )
