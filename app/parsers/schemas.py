from decimal import Decimal

from pydantic import BaseModel


class ProductData(BaseModel):
    product_name: str
    current_price: Decimal
    selected_options: dict[str, str]


class VariantData(BaseModel):
    price: Decimal
    selected_options: dict[str, str]
