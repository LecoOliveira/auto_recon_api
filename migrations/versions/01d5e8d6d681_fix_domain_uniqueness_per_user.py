"""fix domain uniqueness per user

Revision ID: 01d5e8d6d681
Revises: ba31bed671dd
Create Date: 2025-08-30 10:40:14.393494

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '01d5e8d6d681'
down_revision: Union[str, Sequence[str], None] = 'ba31bed671dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
