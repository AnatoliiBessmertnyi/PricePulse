from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, HttpUrl


class SubscriptionCreate(BaseModel):
    user_id: int
    marketplace: str
    product_url: HttpUrl
    target_price: Decimal | None = None


class SubscriptionResponse(BaseModel):
    id: int
    user_id: int
    marketplace: str
    product_url: str
    product_name: str | None
    current_price: Decimal | None
    target_price: Decimal | None
    is_active: bool
    created_at: datetime

    model_config = {
        "from_attributes": True,
    }
