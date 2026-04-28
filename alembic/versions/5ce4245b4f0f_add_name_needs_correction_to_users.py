"""add name_needs_correction to users

Revision ID: 5ce4245b4f0f
Revises: b18da9959263
Create Date: 2026-04-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "5ce4245b4f0f"
down_revision: Union[str, None] = "b18da9959263"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  op.add_column(
    "users",
    sa.Column(
      "name_needs_correction",
      sa.Boolean(),
      nullable=False,
      server_default=sa.false(),
    ),
  )


def downgrade() -> None:
  op.drop_column("users", "name_needs_correction")
