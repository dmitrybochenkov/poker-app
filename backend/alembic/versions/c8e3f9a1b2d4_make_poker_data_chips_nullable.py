"""make poker_data.chips nullable to track "not entered" state

Revision ID: c8e3f9a1b2d4
Revises: b7e8d9f0a1b2
Create Date: 2026-05-15 13:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c8e3f9a1b2d4"
down_revision: Union[str, Sequence[str], None] = "b7e8d9f0a1b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.alter_column(
      "chips",
      existing_type=sa.Integer(),
      nullable=True,
    )


def downgrade() -> None:
  op.execute("UPDATE poker_data SET chips = 0 WHERE chips IS NULL")
  with op.batch_alter_table("poker_data") as batch_op:
    batch_op.alter_column(
      "chips",
      existing_type=sa.Integer(),
      nullable=False,
    )

