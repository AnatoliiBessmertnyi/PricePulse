from structlog import get_logger

from app.parsers.factory import ParserFactory
from app.parsers.exceptions import ParserError
from app.repositories.subscription import SubscriptionRepository
from app.services.price import PriceService


logger = get_logger()


class PriceParsingService:
    def __init__(
        self,
        subscription_repository: SubscriptionRepository,
        parser_factory: ParserFactory,
        price_service: PriceService,
    ) -> None:
        self._subscription_repository = subscription_repository
        self._parser_factory = parser_factory
        self._price_service = price_service

    async def parse_subscription(
        self,
        subscription_id: int,
    ) -> None:
        logger.info(
            "price_parsing_started",
            subscription_id=subscription_id,
        )

        subscription = await self._subscription_repository.get_by_id(
            subscription_id,
        )

        if subscription is None:
            logger.warning(
                "subscription_not_found",
                subscription_id=subscription_id,
            )
            return

        parser = self._parser_factory.create(
            subscription.marketplace,
        )

        try:
            price = await parser.get_price(
                subscription.product_url,
            )
        except ParserError:
            logger.exception(
                "price_parsing_failed",
                subscription_id=subscription_id,
            )
            return

        await self._price_service.save_price(
            subscription_id=subscription.id,
            price=price,
        )

        logger.info(
            "price_saved",
            subscription_id=subscription.id,
            price=str(price),
        )
