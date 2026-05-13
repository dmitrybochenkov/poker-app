"""expand bet tournament tables for historical rows

Revision ID: f1a2b3c4d5e6
Revises: e3b7c1d9a4f2
Create Date: 2026-05-13 21:40:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e3b7c1d9a4f2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  cols_params = _columns("bet_tournament_params")
  if cols_params:
    op.execute(
      sa.text(
        """
        CREATE TABLE bet_tournament_params_new (
          row_id INTEGER NOT NULL PRIMARY KEY,
          tournament_type VARCHAR(16) NOT NULL,
          bet_param_id INTEGER NOT NULL,
          percent_to_first INTEGER NOT NULL DEFAULT 50,
          percent_to_second INTEGER NOT NULL DEFAULT 30,
          percent_to_third INTEGER NOT NULL DEFAULT 20,
          duration_months INTEGER NOT NULL DEFAULT 12
        )
        """
      )
    )
    op.execute(
      sa.text(
        """
        INSERT INTO bet_tournament_params_new (
          row_id, tournament_type, bet_param_id, percent_to_first, percent_to_second, percent_to_third, duration_months
        )
        SELECT row_id, tournament_type, bet_param_id, percent_to_first, percent_to_second, percent_to_third, duration_months
        FROM bet_tournament_params
        """
      )
    )
    op.execute(sa.text("DROP TABLE bet_tournament_params"))
    op.execute(sa.text("ALTER TABLE bet_tournament_params_new RENAME TO bet_tournament_params"))

  cols_tournaments = _columns("bet_tournaments")
  if cols_tournaments:
    bank_col = "current_bank_kopecks" if "current_bank_kopecks" in cols_tournaments else "current_bank_size_kopecks"
    type_col = "tournament_type" if "tournament_type" in cols_tournaments else "NULL"
    op.execute(
      sa.text(
        """
        CREATE TABLE bet_tournaments_new (
          row_id INTEGER NOT NULL PRIMARY KEY,
          params_id INTEGER NOT NULL,
          start_date DATE,
          end_date DATE,
          current_bank_size_kopecks INTEGER NOT NULL DEFAULT 0,
          first_place_name VARCHAR(255),
          second_place_name VARCHAR(255),
          third_place_name VARCHAR(255),
          is_paid BOOLEAN NOT NULL DEFAULT 0,
          tournament_type VARCHAR(16)
        )
        """
      )
    )
    op.execute(
      sa.text(
        f"""
        INSERT INTO bet_tournaments_new (
          row_id, params_id, start_date, end_date, current_bank_size_kopecks,
          first_place_name, second_place_name, third_place_name, is_paid, tournament_type
        )
        SELECT
          row_id,
          COALESCE(params_id, 1),
          NULL,
          NULL,
          COALESCE({bank_col}, 0),
          NULL,
          NULL,
          NULL,
          0,
          {type_col}
        FROM bet_tournaments
        """
      )
    )
    op.execute(sa.text("DROP TABLE bet_tournaments"))
    op.execute(sa.text("ALTER TABLE bet_tournaments_new RENAME TO bet_tournaments"))


def downgrade() -> None:
  # Keep data as-is on downgrade; historical expansion is intentionally non-destructive.
  pass
