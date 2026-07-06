"""add_status_and_task_id_to_subscriptions

Revision ID: 146f5cbf6c6c
Revises: 559cc88eaf9c
Create Date: 2026-07-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "146f5cbf6c6c"
down_revision: str | None = "559cc88eaf9c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Сначала создаём ENUM тип
    op.execute(
        "CREATE TYPE subscriptionstatus AS ENUM ('idle', 'scheduled', 'running', 'completed', 'failed')"
    )

    # Добавляем колонку status
    op.add_column(
        "subscriptions",
        sa.Column(
            "status",
            sa.Enum(
                "idle",
                "scheduled",
                "running",
                "completed",
                "failed",
                name="subscriptionstatus",
            ),
            nullable=False,
            server_default="idle",
        ),
    )

    # Добавляем колонку last_task_id
    op.add_column(
        "subscriptions", sa.Column("last_task_id", sa.String(36), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "last_task_id")
    op.drop_column("subscriptions", "status")
    op.execute("DROP TYPE IF EXISTS subscriptionstatus")
