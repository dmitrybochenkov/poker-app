"""add photo_path to users

Revision ID: c1b2e3f4a5d6
Revises: ea91b7c2d4f0
Create Date: 2026-06-16 16:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c1b2e3f4a5d6"
down_revision: Union[str, Sequence[str], None] = "ea91b7c2d4f0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("users") as batch_op:
    batch_op.add_column(sa.Column("photo_path", sa.String(length=255), nullable=True))


def downgrade() -> None:
  with op.batch_alter_table("users") as batch_op:
    batch_op.drop_column("photo_path")
