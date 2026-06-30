from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_price_service,
    get_subscription_service,
)
from app.api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.services.price import PriceService
from app.services.subscription import SubscriptionService

router = APIRouter(
    prefix="/api/v1/subscriptions",
    tags=["subscriptions"],
)


@router.post(
    "",
    response_model=SubscriptionResponse,
    status_code=201,
)
async def create_subscription(
    data: SubscriptionCreate,
    service: SubscriptionService = Depends(
        get_subscription_service,
    ),
) -> SubscriptionResponse:
    subscription = await service.create_subscription(
        user_id=data.user_id,
        marketplace=data.marketplace,
        product_url=str(data.product_url),
        target_price=data.target_price,
    )

    # Lazy import для избежания circular dependency
    from app.workers.tasks.parse_price import parse_price

    parse_price.delay(subscription.id)

    return SubscriptionResponse.model_validate(
        subscription,
    )


@router.get(
    "/{user_id}",
    response_model=list[SubscriptionResponse],
)
async def get_user_subscriptions(
    user_id: int,
    service: SubscriptionService = Depends(
        get_subscription_service,
    ),
) -> list[SubscriptionResponse]:
    subscriptions = await service.get_user_subscriptions(
        user_id,
    )
    return [
        SubscriptionResponse.model_validate(
            subscription,
        )
        for subscription in subscriptions
    ]


@router.get(
    "/{subscription_id}/prices",
    response_model=list[dict],
)
async def get_price_history(
    subscription_id: int,
    price_service: PriceService = Depends(get_price_service),
) -> list[dict]:
    """Получить историю цен для подписки"""
    history = await price_service.get_price_history(subscription_id)
    return [
        {
            "id": record.id,
            "subscription_id": record.subscription_id,
            "price": float(record.price),
            "created_at": record.created_at.isoformat(),
        }
        for record in history
    ]


@router.post(
    "/{subscription_id}/parse",
    status_code=202,
)
async def trigger_manual_parsing(
    subscription_id: int,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
) -> dict:
    """Ручной запуск парсинга для подписки"""
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    from app.workers.tasks.parse_price import parse_price

    parse_price.delay(subscription_id)

    return {
        "status": "parsing_queued",
        "subscription_id": subscription_id,
    }


@router.get(
    "/{subscription_id}/latest-price",
    response_model=dict,
)
async def get_latest_price(
    subscription_id: int,
    price_service: PriceService = Depends(get_price_service),
) -> dict:
    """Получить последнюю цену для подписки (из кэша или БД)"""
    # Проверяем кэш
    if price_service._redis:
        cache_key = f"price:latest:{subscription_id}"
        cached_price = await price_service._redis.get(cache_key)
        if cached_price:
            return {
                "subscription_id": subscription_id,
                "price": float(cached_price),
                "source": "cache",
            }

    # Если нет в кэше, берем из БД
    price = await price_service.get_latest_price(subscription_id)
    if price is None:
        raise HTTPException(status_code=404, detail="Price not found")

    return {
        "subscription_id": subscription_id,
        "price": float(price),
        "source": "database",
    }

@router.delete(
    "/{subscription_id}",
    status_code=204,
)
async def delete_subscription(
    subscription_id: int,
    user_id: int,
    service: SubscriptionService = Depends(get_subscription_service),
) -> None:
    """Удалить подписку"""
    deleted = await service.delete_subscription(subscription_id, user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Subscription not found")

