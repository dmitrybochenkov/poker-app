"""update law abiding citizen achievement text

Revision ID: a7c4d9e2f1b3
Revises: ff34de56bc78
Create Date: 2026-06-21 16:55:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7c4d9e2f1b3"
down_revision: Union[str, None] = "ff34de56bc78"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


OLD_TEXT = "Законопослушный гражданин_Не имеет неоплаченных ставок в текущий момент времени"
NEW_TEXT = "Законопослушный гражданин_Не имеет неоплаченных ставок в текущем турнире"


def upgrade() -> None:
  op.execute(
    sa.text(
      """
      UPDATE achievements
      SET description = :new_text
      WHERE row_id = 16
        AND type = 'betting'
        AND description = :old_text
      """
    ).bindparams(new_text=NEW_TEXT, old_text=OLD_TEXT)
  )


def downgrade() -> None:
  op.execute(
    sa.text(
      """
      UPDATE achievements
      SET description = :old_text
      WHERE row_id = 16
        AND type = 'betting'
        AND description = :new_text
      """
    ).bindparams(new_text=NEW_TEXT, old_text=OLD_TEXT)
  )
