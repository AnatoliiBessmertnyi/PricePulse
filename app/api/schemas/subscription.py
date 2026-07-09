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
    last_check_at: datetime | None
    last_success_at: datetime | None
    created_at: datetime
    alert_sent: bool
    last_alert_at: datetime | None
    cooldown_hours: int
    model_config = {"from_attributes": True}


class UpdateTargetPrice(BaseModel):
    target_price: Decimal | None
