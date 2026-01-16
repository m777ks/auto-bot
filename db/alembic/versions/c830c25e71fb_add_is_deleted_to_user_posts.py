"""add_is_deleted_to_user_posts

Revision ID: c830c25e71fb
Revises: 8619a94d6906
Create Date: 2026-01-16 18:06:22.002739

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c830c25e71fb'
down_revision: Union[str, None] = '8619a94d6906'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем поля is_deleted и date_deleted в таблицу user_posts
    op.add_column('user_posts', sa.Column('is_deleted', sa.Boolean(), nullable=True, default=False))
    op.add_column('user_posts', sa.Column('date_deleted', sa.DateTime(timezone=True), nullable=True))
    
    # Устанавливаем значение по умолчанию для существующих записей
    op.execute("UPDATE user_posts SET is_deleted = FALSE WHERE is_deleted IS NULL")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user_posts', 'date_deleted')
    op.drop_column('user_posts', 'is_deleted')
