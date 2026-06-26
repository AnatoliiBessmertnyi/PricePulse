from sqlalchemy.ext.asyncio import AsyncSession

from app.parsers.factory import ParserFactory
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.price import PriceService
from app.services.price_parsing import PriceParsingService


def get_price_parsing_service(
    session: AsyncSession,
) -> PriceParsingService:
    subscription_repository = SubscriptionRepository(session)
    price_history_repository = PriceHistoryRepository(session)

    parser_factory = ParserFactory()

    price_service = PriceService(
        price_history_repository=price_history_repository,
    )

    return PriceParsingService(
        subscription_repository=subscription_repository,
        parser_factory=parser_factory,
        price_service=price_service,
    )
