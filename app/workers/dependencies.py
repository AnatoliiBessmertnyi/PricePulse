from sqlalchemy.ext.asyncio import AsyncSession as SQLAlchemyAsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.redis import get_redis_sync
from app.parsers.factory import ParserFactory
from app.parsers.http_client import MarketplaceHttpClient
from app.proxy.service import ProxyService
from app.repositories.parse_error import ParseErrorRepository
from app.repositories.price_history import PriceHistoryRepository
from app.repositories.subscription import SubscriptionRepository
from app.services.price import PriceCache, PriceService
from app.services.price_parsing import PriceParsingService
from app.services.subscription import SubscriptionService
from app.workers.http_client_manager import get_process_browser

logger = get_logger(__name__)


async def get_price_parsing_service(
    session: SQLAlchemyAsyncSession,
) -> PriceParsingService:
    """Создать сервис парсинга с браузером текущего процесса."""
    subscription_repository = SubscriptionRepository(session)
    price_history_repository = PriceHistoryRepository(session)
    parse_error_repository = ParseErrorRepository(session)
    browser_manager = get_process_browser()
    proxy_service = None
    if settings.proxy_rotation_enabled and settings.proxy_list_parsed:
        proxy_service = ProxyService(proxy_urls=settings.proxy_list_parsed)

    marketplace_http_client = MarketplaceHttpClient(
        browser_manager=browser_manager, proxy_service=proxy_service
    )
    parser_factory = ParserFactory(http_client=marketplace_http_client)
    redis_client_sync = get_redis_sync()
    price_cache = PriceCache(redis_sync=redis_client_sync)
    price_service = PriceService(
        price_history_repository=price_history_repository, price_cache=price_cache
    )
    return PriceParsingService(
        subscription_repository=subscription_repository,
        parser_factory=parser_factory,
        price_service=price_service,
        parse_error_repository=parse_error_repository,
    )


def get_subscription_service(session: SQLAlchemyAsyncSession) -> SubscriptionService:
    subscription_repository = SubscriptionRepository(session)
    return SubscriptionService(subscription_repository=subscription_repository)
