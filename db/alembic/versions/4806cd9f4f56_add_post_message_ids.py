"""add_post_message_ids

Revision ID: 4806cd9f4f56
Revises: c830c25e71fb
Create Date: 2026-01-16

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '4806cd9f4f56'
down_revision: Union[str, None] = 'c830c25e71fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поле post_message_ids для хранения всех message_id медиагруппы
    op.add_column('user_posts', sa.Column('post_message_ids', postgresql.ARRAY(sa.BigInteger()), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_posts', 'post_message_ids')
