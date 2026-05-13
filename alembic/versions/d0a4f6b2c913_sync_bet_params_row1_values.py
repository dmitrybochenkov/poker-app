"""sync bet_params row1 values

Revision ID: d0a4f6b2c913
Revises: cf72ab98de11
Create Date: 2026-05-13 14:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "d0a4f6b2c913"
down_revision: Union[str, None] = "cf72ab98de11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  bind = op.get_bind()
  exists = bind.execute(sa.text("SELECT 1 FROM bet_params WHERE row_id = 1")).fetchone()
  if exists is None:
    bind.execute(
      sa.text(
        """
        INSERT INTO bet_params (
          row_id,
          small_pic,
          small_size_kopecks,
          small_score,
          small_score_combo,
          big_pic,
          big_size_kopecks,
          big_score,
          big_score_combo,
          percent_to_regular_bank_if_it_is_going
        ) VALUES (
          1, '🐤', 20000, 1, 3, '🐔', 40000, 2, 5, 80
        )
        """
      )
    )
  else:
    bind.execute(
      sa.text(
        """
        UPDATE bet_params
        SET
          small_pic = '🐤',
          small_size_kopecks = 20000,
          small_score = 1,
          small_score_combo = 3,
          big_pic = '🐔',
          big_size_kopecks = 40000,
          big_score = 2,
          big_score_combo = 5,
          percent_to_regular_bank_if_it_is_going = 80
        WHERE row_id = 1
        """
      )
    )


def downgrade() -> None:
  pass

