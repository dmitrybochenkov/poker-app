"""add winners and loosers to pokers

Revision ID: d1f7a9c3e5b2
Revises: c4e8f2a1b6d7
Create Date: 2026-05-12 10:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d1f7a9c3e5b2"
down_revision: Union[str, Sequence[str], None] = "c4e8f2a1b6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column("pokers", sa.Column("winners", sa.Text(), nullable=True))
  op.add_column("pokers", sa.Column("loosers", sa.Text(), nullable=True))


def downgrade() -> None:
  op.drop_column("pokers", "loosers")
  op.drop_column("pokers", "winners")
