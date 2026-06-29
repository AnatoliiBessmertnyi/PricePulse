from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_sync
from app.parsers.factory import ParserFactory
from app.parsers.http_client import MarketplaceHttpClient
from app.repositories.parse_error import ParseErrorRepository
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.price import PriceService
from app.services.price_parsing import PriceParsingService
from app.services.subscription import SubscriptionService
from app.workers.http_client_manager import get_http_client


def get_price_parsing_service(
    session: AsyncSession,
) -> PriceParsingService:
    subscription_repository = SubscriptionRepository(session)
    price_history_repository = PriceHistoryRepository(session)
    parse_error_repository = ParseErrorRepository(session)
    httpx_client = get_http_client()
    marketplace_http_client = MarketplaceHttpClient(http_client=httpx_client)
    parser_factory = ParserFactory(http_client=marketplace_http_client)
    redis_client_sync = get_redis_sync()
    price_service = PriceService(
        price_history_repository=price_history_repository,
        redis_client_sync=redis_client_sync,
    )

    return PriceParsingService(
        subscription_repository=subscription_repository,
        parser_factory=parser_factory,
        price_service=price_service,
        parse_error_repository=parse_error_repository,
    )


def get_subscription_service(
    session: AsyncSession,
) -> SubscriptionService:
    subscription_repository = SubscriptionRepository(session)

    return SubscriptionService(
        subscription_repository=subscription_repository,
    )
