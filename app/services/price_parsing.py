from datetime import UTC, datetime
from decimal import Decimal

from app.core.config import settings
from app.core.constants import ERROR_MESSAGE_MAX_LENGTH
from app.core.logging import get_logger
from app.models.subscription import Subscription, SubscriptionStatus
from app.parsers.exceptions import ParserError, ProductDataNotFoundError
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

    async def parse_subscription(self, subscription_id: int) -> bool:
        """Возвращает True, если подписка активна, False если она была архивирована."""
        subscription = await self._subscription_repository.get(subscription_id)
        if subscription is None:
            logger.warning("subscription_not_found", subscription_id=subscription_id)
            return False

        parser = self._parser_factory.get_parser(subscription.marketplace)
        now = datetime.now(UTC)

        try:
            product_data = await parser.parse(subscription.product_url)
            price = product_data.current_price
            subscription.consecutive_errors = 0
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
                        "notification_error",
                        subscription_id=subscription.id,
                        error=str(e),
                    )

            if product_data.product_name:
                subscription.product_name = product_data.product_name

            await self._subscription_repository.session.commit()
            logger.info(
                "price_saved", subscription_id=subscription.id, price=str(price)
            )
            return True

        except ProductDataNotFoundError as e:
            subscription.consecutive_errors += 1
            error_msg = str(e)
            if "Товар не найден или удален: " in error_msg:
                subscription.product_name = error_msg.replace(
                    "Товар не найден или удален: ", ""
                ).strip()

            logger.warning(
                "product_not_found_archiving_progress",
                subscription_id=subscription_id,
                errors=subscription.consecutive_errors,
                max_errors=settings.max_consecutive_errors,
                error_message=error_msg[:100],
            )

            if subscription.consecutive_errors >= settings.max_consecutive_errors:
                subscription.status = SubscriptionStatus.ARCHIVED
                await self._subscription_repository.session.commit()
                try:
                    NotificationService().notify_subscription_archived(subscription)
                except Exception as notify_err:
                    logger.error(
                        "archive_notification_failed",
                        subscription_id=subscription_id,
                        error=str(notify_err),
                    )
                return False

            await self._parse_error_repository.create(
                subscription_id=subscription_id,
                error_type="ProductDataNotFoundError",
                error_message=error_msg[:ERROR_MESSAGE_MAX_LENGTH],
            )
            await self._subscription_repository.session.commit()
            raise

        except Exception as e:
            is_parser_error = isinstance(e, ParserError)
            error_message = (
                str(e) if is_parser_error else str(e)[:ERROR_MESSAGE_MAX_LENGTH]
            )
            logger.exception(
                (
                    "price_parsing_failed"
                    if is_parser_error
                    else "unexpected_parsing_error"
                ),
                subscription_id=subscription_id,
            )
            subscription.consecutive_errors += 1
            if subscription.consecutive_errors >= settings.max_consecutive_errors:
                subscription.status = SubscriptionStatus.ARCHIVED
                await self._subscription_repository.session.commit()

                try:
                    NotificationService().notify_subscription_archived(subscription)
                except Exception as notify_err:
                    logger.error(
                        "archive_notification_failed",
                        subscription_id=subscription_id,
                        error=str(notify_err),
                    )

                logger.warning(
                    "subscription_archived",
                    subscription_id=subscription_id,
                    errors=subscription.consecutive_errors,
                )
                return False

            await self._parse_error_repository.create(
                subscription_id=subscription_id,
                error_type=type(e).__name__,
                error_message=error_message,
            )
            await self._subscription_repository.session.commit()
            raise

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
