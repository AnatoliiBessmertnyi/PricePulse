from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.subscription import Subscription


class ParseError(Base, TimestampMixin):
    __tablename__ = "parse_errors"

    id: Mapped[int] = mapped_column(
        primary_key=True,
    )

    subscription_id: Mapped[int] = mapped_column(
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    error_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )

    error_message: Mapped[str] = mapped_column(
        String(2048),
        nullable=False,
    )

    subscription: Mapped["Subscription"] = relationship(
        back_populates="parse_errors",
    )
