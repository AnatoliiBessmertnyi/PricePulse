from fastapi import APIRouter, Depends, HTTPException

from app.api.dependencies import (
    get_cache_service,
    get_price_service,
    get_subscription_service,
)
from app.api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
    UpdateTargetPrice,
)
from app.core.cache import CacheService
from app.services.price import PriceService
from app.services.subscription import SubscriptionService
from app.workers.tasks.parse_price import parse_price

router = APIRouter(prefix="/api/v1/subscriptions", tags=["subscriptions"])


@router.post("", response_model=SubscriptionResponse, status_code=201)
async def create_subscription(
    data: SubscriptionCreate,
    service: SubscriptionService = Depends(get_subscription_service),
) -> SubscriptionResponse:
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
    cache_key = f"subs:user:{user_id}"
    cached_data = await cache.get_json(cache_key)
    if cached_data:
        return [SubscriptionResponse.model_validate(item) for item in cached_data]

    subscriptions = await service.get_user_subscriptions(user_id)
    data_to_cache = [
        SubscriptionResponse.model_validate(sub).model_dump() for sub in subscriptions
    ]
    await cache.set_json(cache_key, data_to_cache, ttl=30)
    return [SubscriptionResponse.model_validate(sub) for sub in subscriptions]


@router.get("/{subscription_id}/prices", response_model=list[dict])
async def get_price_history(
    subscription_id: int,
    price_service: PriceService = Depends(get_price_service),
    cache: CacheService = Depends(get_cache_service),
) -> list[dict]:
    cache_key = f"prices:history:{subscription_id}"
    cached_data = await cache.get_json(cache_key)
    if cached_data:
        return cached_data

    history = await price_service.get_price_history(subscription_id)
    data_to_cache = [
        {
            "id": record.id,
            "subscription_id": record.subscription_id,
            "price": float(record.price),
            "created_at": record.created_at.isoformat(),
        }
        for record in history
    ]
    await cache.set_json(cache_key, data_to_cache, ttl=60)
    return data_to_cache


@router.post("/{subscription_id}/parse", status_code=202)
async def trigger_manual_parsing(
    subscription_id: int,
    subscription_service: SubscriptionService = Depends(get_subscription_service),
) -> dict:
    subscription = await subscription_service.get_subscription(subscription_id)
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    parse_price.delay(subscription_id)
    return {"status": "parsing_queued", "subscription_id": subscription_id}


@router.get("/{subscription_id}/latest-price", response_model=dict)
async def get_latest_price(
    subscription_id: int, price_service: PriceService = Depends(get_price_service)
) -> dict:
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
    """Удалить подписку"""
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
    """Обновить target_price для подписки"""
    subscription = await service.update_target_price(
        subscription_id=subscription_id, user_id=user_id, target_price=data.target_price
    )
    if not subscription:
        raise HTTPException(status_code=404, detail="Subscription not found")

    return SubscriptionResponse.model_validate(subscription)
