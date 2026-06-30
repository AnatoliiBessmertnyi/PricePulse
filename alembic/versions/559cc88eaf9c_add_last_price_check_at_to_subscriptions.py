"""add_last_price_check_at_to_subscriptions

Revision ID: 559cc88eaf9c
Revises: 01e6210595b9
Create Date: 2026-06-30 10:51:06.474630

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '559cc88eaf9c'
down_revision: Union[str, Sequence[str], None] = '01e6210595b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('subscriptions', sa.Column('last_price_check_at', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('subscriptions', 'last_price_check_at')
