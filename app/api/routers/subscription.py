from fastapi import APIRouter, Depends

from app.api.dependencies import (
    get_subscription_service,
)
from app.api.schemas.subscription import (
    SubscriptionCreate,
    SubscriptionResponse,
)
from app.services.subscription import (
    SubscriptionService,
)

router = APIRouter(
    prefix="/api/v1/subscriptions",
    tags=["subscriptions"],
)


@router.post(
    "",
    response_model=SubscriptionResponse,
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
