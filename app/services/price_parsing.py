from datetime import UTC, datetime
from decimal import Decimal

from app.core.constants import ERROR_MESSAGE_MAX_LENGTH
from app.core.logging import get_logger
from app.models.subscription import Subscription
from app.parsers.exceptions import ParserError
from app.parsers.factory import ParserFactory
from app.repositories.parse_error import ParseErrorRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.notification import NotificationService
from app.services.price import PriceService

logger = get_logger(__name__)


class PriceParsingService:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        parser_factory: ParserFactory,
        price_service: PriceService,
        parse_error_repository: ParseErrorRepository,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._parser_factory = parser_factory
        self._price_service = price_service
        self._parse_error_repository = parse_error_repository

    async def parse_subscription(self, subscription_id: int) -> None:
        subscription = await self._subscription_repository.get(subscription_id)

        if subscription is None:
            logger.warning("subscription_not_found", subscription_id=subscription_id)
            return

        parser = self._parser_factory.get_parser(subscription.marketplace)
        now = datetime.now(UTC)

        try:
            product_data = await parser.parse(subscription.product_url)
            price = product_data.current_price
        except Exception as e:
            is_parser_error = isinstance(e, ParserError)
            error_message = (
                str(e) if is_parser_error else str(e)[:ERROR_MESSAGE_MAX_LENGTH]
            )
            logger_name = (
                "price_parsing_failed"
                if is_parser_error
                else "unexpected_parsing_error"
            )
            logger.exception(logger_name, subscription_id=subscription_id)
            await self._parse_error_repository.create(
                subscription_id=subscription_id,
                error_type=type(e).__name__,
                error_message=error_message,
            )
            await self._subscription_repository.session.commit()
            raise

        await self._price_service.save_price(
            subscription_id=subscription.id, price=price
        )
        subscription.current_price = price
        subscription.last_success_at = now

        if self._should_send_alert(subscription, price):
            try:
                notification_service = NotificationService()
                notification_service.notify_price_drop(subscription)
                subscription.alert_sent = True
            except Exception as e:
                logger.error(
                    "notification_error", subscription_id=subscription.id, error=str(e)
                )

        if product_data.product_name:
            subscription.product_name = product_data.product_name

        await self._subscription_repository.session.commit()

        logger.info(
            "price_saved",
            subscription_id=subscription.id,
            price=str(price),
            product_name=product_data.product_name,
        )

    def _should_send_alert(
        self, subscription: Subscription, new_price: Decimal
    ) -> bool:
        """
        Проверить, нужно ли отправить уведомление о снижении цены.

        Условие:
        - target_price установлен
        - новая цена <= target_price
        - уведомление еще не было отправлено (alert_sent = False)
        """
        if subscription.target_price is None:
            return False

        if subscription.alert_sent:
            return False

        return new_price <= subscription.target_price
