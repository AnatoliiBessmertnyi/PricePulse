import httpx
import structlog
from pydantic import BaseModel

from app.bot.config import bot_settings

logger = structlog.get_logger()


class UserCreateRequest(BaseModel):
    chat_id: int
    username: str | None = None


class SubscriptionCreateRequest(BaseModel):
    user_id: int
    marketplace: str
    product_url: str
    target_price: float | None = None


class HTTPClient:
    """HTTP клиент для взаимодействия с FastAPI"""

    def __init__(self):
        self.base_url = bot_settings.fastapi_base_url
        self.timeout = httpx.Timeout(
            bot_settings.request_timeout,
            connect=bot_settings.connect_timeout,
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=self.timeout,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> httpx.Response:
        """Универсальный метод для HTTP запросов"""
        if not self._client:
            raise RuntimeError("HTTP client not initialized")

        url = f"{self.base_url}{path}"
        logger.info(
            "api_request",
            method=method,
            url=url,
            **{k: v for k, v in kwargs.items() if k != "json"},
        )

        try:
            response = await self._client.request(method, path, **kwargs)
            logger.info(
                "api_response",
                method=method,
                url=url,
                status_code=response.status_code,
            )
            return response
        except httpx.RequestError as e:
            logger.error(
                "api_request_failed",
                method=method,
                url=url,
                error=str(e),
            )
            raise

    async def create_user(
        self,
        chat_id: int,
        username: str | None = None,
    ) -> dict:
        """Создать пользователя или получить существующего"""
        data = UserCreateRequest(
            chat_id=chat_id,
            username=username,
        )
        response = await self._request(
            "POST",
            "/api/v1/users",
            json=data.model_dump(),
        )
        response.raise_for_status()
        return response.json()

    async def get_user_subscriptions(
        self,
        user_id: int,
    ) -> list[dict]:
        """Получить список подписок пользователя"""
        response = await self._request(
            "GET",
            f"/api/v1/subscriptions/{user_id}",
        )
        response.raise_for_status()
        return response.json()

    async def create_subscription(
        self,
        user_id: int,
        marketplace: str,
        product_url: str,
        target_price: float | None = None,
    ) -> dict:
        """Создать подписку на товар"""
        data = SubscriptionCreateRequest(
            user_id=user_id,
            marketplace=marketplace,
            product_url=product_url,
            target_price=target_price,
        )
        response = await self._request(
            "POST",
            "/api/v1/subscriptions",
            json=data.model_dump(),
        )
        response.raise_for_status()
        return response.json()
