from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin
from app.models.user import User

if TYPE_CHECKING:
    from app.models.parse_error import ParseError
    from app.models.price_history import PriceHistory


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
        String(2000),
        nullable=False,
    )

    product_name: Mapped[str | None] = mapped_column(
        String(500),
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

    last_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    user: Mapped[User] = relationship(
        back_populates="subscriptions",
    )

    parse_errors: Mapped[list["ParseError"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )

    price_history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="subscription",
        cascade="all, delete-orphan",
    )
