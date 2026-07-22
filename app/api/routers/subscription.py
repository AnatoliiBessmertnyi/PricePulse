import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response

from app.api.dependencies import (
    get_cache_service,
    get_price_chart_service,
    get_price_service,
    get_subscription_service,
)
from app.api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    UpdateCooldown,
    UpdateTargetPrice,
)
from app.core.cache import CacheService
from app.core.config import settings
from app.core.logging import get_logger
from app.services.price import PriceService
from app.services.price_chart import PriceChartService
from app.services.subscription import SubscriptionService
from app.workers.tasks.parse_price import parse_price

logger = get_logger(__name__)
router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionResponse:
    """Создает новую подписку на отслеживание цены."""
    subscription = await service.create_subscription(
        user_id=data.user_id,
        marketplace=data.marketplace,
        product_url=str(data.product_url),
        target_price=data.target_price,
    )
    return SubscriptionResponse.model_validate(subscription)


@router.get("/{user_id}", response_model=list[SubscriptionResponse])
async def get_user_subscriptions(
    user_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
    cache: CacheService = Depends(get_cache_service),
) -> list[SubscriptionResponse]:
    """Получает список подписок пользователя с кэшированием результата."""
    cache_key = f"subs:user:{user_id}"
    cached_data = await cache.get_json(cache_key)
    if cached_data:
        return [SubscriptionResponse.model_validate(item) for item in cached_data]

    subscriptions = await service.get_user_subscriptions(user_id)
    data_to_cache = [
        SubscriptionResponse.model_validate(sub).model_dump(mode="json")
        for sub in subscriptions
    ]
    await cache.set_json(cache_key, data_to_cache, ttl=30)
    return [SubscriptionResponse.model_validate(sub) for sub in subscriptions]


@router.get("/{subscription_id}/prices", response_model=list[dict])
async def get_price_history(
    subscription_id: int,
    period: str = Query(default="7d", pattern="^(24h|7d|30d|all)$"),
    price_service: PriceService = Depends(get_price_service),
) -> list[dict]:
    """Получает агрегированную историю цен за указанный период."""
    return await price_service.get_price_history(subscription_id, period)


@router.post("/{subscription_id}/parse", status_code=202)
async def trigger_manual_parsing(
    subscription_id: int,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
) -> dict:
    """Запускает задачу парсинга цены для подписки в фоновом режиме."""
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    parse_price.delay(subscription_id)
    return {"status": "parsing_queued", "subscription_id": subscription_id}


@router.get("/{subscription_id}/latest-price", response_model=dict)
async def get_latest_price(
    subscription_id: int, price_service: PriceService = Depends(get_price_service)
) -> dict:
    """Получает последнюю известную цену для указанной подписки."""
    price = await price_service.get_latest_price(subscription_id)
    if price is None:
        raise HTTPException(status_code=404, detail="Price not found")

    return {
        "subscription_id": subscription_id,
        "price": float(price),
        "source": "service_cache_or_db",
    }


@router.delete("/{subscription_id}", status_code=204)
async def delete_subscription(
    subscription_id: int,
    user_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
) -> None:
    """Удаляет подписку пользователя по идентификатору."""
    deleted = await service.delete_subscription(subscription_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")


@router.patch("/{subscription_id}/target-price", response_model=SubscriptionResponse)
async def update_target_price(
    subscription_id: int,
    user_id: int,
    data: UpdateTargetPrice,
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionResponse:
    """Обновляет целевую цену для указанной подписки."""
    subscription = await service.update_target_price(
        subscription_id=subscription_id, user_id=user_id, target_price=data.target_price
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return SubscriptionResponse.model_validate(subscription)


@router.get("/{user_id}/archived", response_model=list[SubscriptionResponse])
async def get_archived_subscriptions(
    user_id: int, service: SubscriptionService = Depends(get_subscription_service)
) -> list[SubscriptionResponse]:
    """Получает список архивных подписок пользователя."""
    subscriptions = await service.get_archived_subscriptions(user_id)
    return [SubscriptionResponse.model_validate(item) for item in subscriptions]


@router.post("/{subscription_id}/reactivate", response_model=SubscriptionResponse)
async def reactivate_subscription(
    subscription_id: int,
    user_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionResponse:
    """Реактивирует архивную подписку пользователя."""
    success = await service.reactivate_subscription(subscription_id, user_id)
    if not success:
        raise HTTPException(
            status_code=404, detail="Subscription not found or not archived"
        )

    subscription = await service.get_subscription(subscription_id)
    return SubscriptionResponse.model_validate(subscription)


@router.patch("/{subscription_id}/cooldown", response_model=SubscriptionResponse)
async def update_cooldown(
    subscription_id: int,
    user_id: int,
    data: UpdateCooldown,
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionResponse:
    """Обновляет период задержки уведомлений для указанной подписки."""
    subscription = await service.update_cooldown(
        subscription_id=subscription_id,
        user_id=user_id,
        cooldown_hours=data.cooldown_hours,
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return SubscriptionResponse.model_validate(subscription)


@router.get("/{subscription_id}/chart")
async def get_chart(
    subscription_id: int,
    period: str = Query(default="7d", pattern="^(7d|30d|all)$"),
    user_id: int = Query(..., description="ID пользователя для проверки прав"),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    chart_service: PriceChartService = Depends(get_price_chart_service),
) -> Response:
    """Генерирует и возвращает изображение графика цен за указанный период."""
    logger.info(
        "chart_generation_started", subscription_id=subscription_id, period=period
    )
    try:
        subscription = await subscription_service.get_subscription(subscription_id)
        if not subscription or subscription.user_id != user_id:
            logger.warning(
                "chart_unauthorized", subscription_id=subscription_id, user_id=user_id
            )
            raise HTTPException(status_code=404, detail="Subscription not found")

        chart_bytes = await chart_service.get_chart_image(
            subscription_id=subscription_id,
            period=period,
            target_price=subscription.target_price,
        )

        if not chart_bytes:
            logger.info("chart_no_data", subscription_id=subscription_id)
            raise HTTPException(
                status_code=404,
                detail=(
                    "Недостаточно данных для построения графика (требуется минимум "
                    "2 точки)"
                ),
            )

        logger.info(
            "chart_generation_success",
            subscription_id=subscription_id,
            size_bytes=len(chart_bytes),
        )
        return Response(content=chart_bytes, media_type="image/png")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "chart_generation_failed",
            subscription_id=subscription_id,
            error=str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=500, detail="Внутренняя ошибка при генерации графика"
        ) from e


@router.post("/{subscription_id}/chart/send")
async def send_chart_to_telegram(
    subscription_id: int,
    chat_id: int = Query(...),
    period: str = Query(default="7d", pattern="^(7d|30d|all)$"),
    user_id: int = Query(...),
    caption: str = Query(...),
    reply_markup: str = Query(...),
    subscription_service: SubscriptionService = Depends(get_subscription_service),
    chart_service: PriceChartService = Depends(get_price_chart_service),
) -> dict:
    """Генерирует график и отправляет его в Telegram через API."""
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription or subscription.user_id != user_id:
        raise HTTPException(status_code=404, detail="Subscription not found")

    chart_bytes = await chart_service.get_chart_image(
        subscription_id=subscription_id,
        period=period,
        target_price=subscription.target_price,
    )
    proxy_url = (settings.telegram_api_url or "https://api.telegram.org").rstrip("/")
    token = settings.telegram_bot_token

    try:
        if not chart_bytes:
            url = f"{proxy_url}/bot{token}/sendMessage"
            data = {
                "chat_id": chat_id,
                "text": caption
                + "\n\n⚠️ Недостаточно данных для построения графика (мин. 2 точки).",
                "parse_mode": "Markdown",
                "reply_markup": reply_markup,
            }
            async with httpx.AsyncClient(timeout=15.0) as client:
                await client.post(url, json=data)
            return {"status": "no_data"}

        url = f"{proxy_url}/bot{token}/sendPhoto"
        files = {"photo": ("chart.png", chart_bytes, "image/png")}
        data = {
            "chat_id": chat_id,
            "caption": caption,
            "parse_mode": "Markdown",
            "reply_markup": reply_markup,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, data=data, files=files)
            response.raise_for_status()

        logger.info(
            "chart_sent_to_telegram", subscription_id=subscription_id, chat_id=chat_id
        )
        return {"status": "ok"}

    except Exception as e:
        logger.error(
            "telegram_send_photo_failed", subscription_id=subscription_id, error=str(e)
        )
        raise HTTPException(
            status_code=500, detail="Failed to send chart to Telegram"
        ) from e
