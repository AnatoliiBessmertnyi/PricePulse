"""add alert_sent to subscriptions

Revision ID: d52f2823cf5f
Revises: be21a0b854c2
Create Date: 2026-07-06 09:01:33.647105

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d52f2823cf5f"
down_revision: str | Sequence[str] | None = "be21a0b854c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add alert_sent column to subscriptions table."""
    op.add_column(
        "subscriptions",
        sa.Column(
            "alert_sent",
            sa.Boolean(),
            nullable=False,
            server_default="false",
            comment="Было ли отправлено уведомление о достижении target_price",
        ),
    )


def downgrade() -> None:
    """Remove alert_sent column from subscriptions table."""
    op.drop_column("subscriptions", "alert_sent")
