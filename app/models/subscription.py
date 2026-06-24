from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.parse_error import ParseError
    from app.models.price_history import PriceHistory
    from app.models.user import User


class Subscription(Base, TimestampMixin):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    marketplace: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    product_url: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    product_name: Mapped[str | None] = mapped_column(
        String(512),
        nullable=True,
    )

    current_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    target_price: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2),
        nullable=True,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    user: Mapped["User"] = relationship(
        back_populates="subscriptions",
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    parse_errors: Mapped[list["ParseError"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
