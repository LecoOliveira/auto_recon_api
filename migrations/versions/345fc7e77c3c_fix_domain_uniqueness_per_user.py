"""fix domain uniqueness per user

Revision ID: 345fc7e77c3c
Revises: 01d5e8d6d681
Create Date: 2025-08-30 11:01:02.705780

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '345fc7e77c3c'
down_revision: Union[str, Sequence[str], None] = '01d5e8d6d681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
