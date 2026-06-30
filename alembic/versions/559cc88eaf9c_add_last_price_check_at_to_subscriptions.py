"""add_last_price_check_at_to_subscriptions

Revision ID: 559cc88eaf9c
Revises: 01e6210595b9
Create Date: 2026-06-30 10:51:06.474630

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "559cc88eaf9c"
down_revision: str | Sequence[str] | None = "01e6210595b9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("last_check_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "subscriptions",
        sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "last_success_at")
    op.drop_column("subscriptions", "last_check_at")
