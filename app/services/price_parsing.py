from datetime import datetime

from app.core.logging import get_logger
from app.parsers.exceptions import ParserError
from app.parsers.factory import ParserFactory
from app.repositories.parse_error import ParseErrorRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.price import PriceService
from app.workers.http_client_manager import close_page

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
        self._page = None  # Будет установлен в get_price_parsing_service

    async def parse_subscription(
        self,
        subscription_id: int,
    ) -> None:
        logger.info("price_parsing_started", subscription_id=subscription_id)

        subscription = await self._subscription_repository.get(subscription_id)

        if subscription is None:
            logger.warning(
                "subscription_not_found",
                subscription_id=subscription_id,
            )
            return

        try:
            parser = self._parser_factory.get_parser(subscription.marketplace)
            now = datetime.utcnow()
            subscription.last_check_at = now

            try:
                product_data = await parser.parse(subscription.product_url)
                price = product_data.current_price
            except ParserError as e:
                logger.exception("price_parsing_failed", subscription_id=subscription_id)

                await self._parse_error_repository.create(
                    subscription_id=subscription_id,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
                await self._subscription_repository.session.commit()
                return
            except Exception as e:
                logger.exception(
                    "unexpected_parsing_error", subscription_id=subscription_id
                )

                await self._parse_error_repository.create(
                    subscription_id=subscription_id,
                    error_type=type(e).__name__,
                    error_message=str(e)[:200],
                )
                await self._subscription_repository.session.commit()
                return

            await self._price_service.save_price(
                subscription_id=subscription.id,
                price=price,
            )

            subscription.current_price = price
            subscription.last_success_at = now
            if product_data.product_name:
                subscription.product_name = product_data.product_name

            await self._subscription_repository.session.commit()

            logger.info(
                "price_saved",
                subscription_id=subscription.id,
                price=str(price),
                product_name=product_data.product_name,
            )
        finally:
            # Закрываем страницу после завершения задачи
            if self._page:
                await close_page(self._page)
