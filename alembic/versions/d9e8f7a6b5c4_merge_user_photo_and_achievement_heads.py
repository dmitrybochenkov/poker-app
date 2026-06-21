"""merge user photo and achievement heads

Revision ID: d9e8f7a6b5c4
Revises: c1b2e3f4a5d6, a7c4d9e2f1b3
Create Date: 2026-06-21 18:05:00.000000
"""

from typing import Sequence, Union


# revision identifiers, used by Alembic.
revision: str = "d9e8f7a6b5c4"
down_revision: Union[str, Sequence[str], None] = ("c1b2e3f4a5d6", "a7c4d9e2f1b3")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
  pass


def downgrade() -> None:
  pass
