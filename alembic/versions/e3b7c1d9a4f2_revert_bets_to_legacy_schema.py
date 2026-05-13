"""revert bets to legacy schema

Revision ID: e3b7c1d9a4f2
Revises: d0a4f6b2c913
Create Date: 2026-05-13 21:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e3b7c1d9a4f2"
down_revision: str | Sequence[str] | None = "d0a4f6b2c913"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _columns(table_name: str) -> set[str]:
  bind = op.get_bind()
  rows = bind.execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
  return {str(row[1]) for row in rows}


def upgrade() -> None:
  cols = _columns("bets")
  if not {"poker_id", "tournament_type"}.intersection(cols):
    return

  op.execute(sa.text("DROP INDEX IF EXISTS ix_bets_date"))
  op.execute(sa.text("DROP INDEX IF EXISTS ix_bets_better_id"))
  op.execute(sa.text("DROP INDEX IF EXISTS ix_bets_poker_id"))
  op.execute(sa.text("DROP INDEX IF EXISTS uq_bets_date_better_name"))

  op.execute(
    sa.text(
      """
      CREATE TABLE bets_legacy (
        row_id INTEGER NOT NULL PRIMARY KEY,
        params_id INTEGER,
        date DATE,
        better_name VARCHAR(255) NOT NULL,
        better_id INTEGER NOT NULL,
        size_kopecks INTEGER NOT NULL,
        winner VARCHAR(255),
        looser VARCHAR(255),
        score INTEGER NOT NULL DEFAULT 0,
        is_paid BOOLEAN NOT NULL DEFAULT 0
      )
      """
    )
  )

  op.execute(
    sa.text(
      """
      INSERT INTO bets_legacy (row_id, params_id, date, better_name, better_id, size_kopecks, winner, looser, score, is_paid)
      SELECT row_id, params_id, date, better_name, better_id, size_kopecks, winner, looser, score, is_paid
      FROM bets
      """
    )
  )

  op.execute(sa.text("DROP TABLE bets"))
  op.execute(sa.text("ALTER TABLE bets_legacy RENAME TO bets"))
  op.execute(sa.text("CREATE INDEX ix_bets_date ON bets (date)"))


def downgrade() -> None:
  cols = _columns("bets")
  if "poker_id" in cols and "tournament_type" in cols:
    return

  op.execute(sa.text("DROP INDEX IF EXISTS ix_bets_date"))

  op.execute(
    sa.text(
      """
      CREATE TABLE bets_new (
        row_id INTEGER NOT NULL PRIMARY KEY,
        poker_id INTEGER NOT NULL,
        better_id INTEGER NOT NULL,
        better_name VARCHAR(255) NOT NULL,
        tournament_type VARCHAR(16) NOT NULL,
        size_kopecks INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
        params_id INTEGER,
        winner VARCHAR(255),
        looser VARCHAR(255),
        score INTEGER NOT NULL DEFAULT 0,
        date DATE,
        is_paid BOOLEAN NOT NULL DEFAULT 0,
        FOREIGN KEY(poker_id) REFERENCES pokers (row_id) ON DELETE CASCADE,
        CONSTRAINT uq_bets_poker_better_tournament UNIQUE (poker_id, better_id, tournament_type)
      )
      """
    )
  )

  op.execute(
    sa.text(
      """
      INSERT INTO bets_new (row_id, poker_id, better_id, better_name, tournament_type, size_kopecks, params_id, winner, looser, score, date, is_paid)
      SELECT
        b.row_id,
        COALESCE((SELECT p.row_id FROM pokers p WHERE p.date = b.date ORDER BY p.row_id DESC LIMIT 1), 1) AS poker_id,
        b.better_id,
        b.better_name,
        'regular' AS tournament_type,
        b.size_kopecks,
        b.params_id,
        b.winner,
        b.looser,
        b.score,
        b.date,
        b.is_paid
      FROM bets b
      """
    )
  )

  op.execute(sa.text("DROP TABLE bets"))
  op.execute(sa.text("ALTER TABLE bets_new RENAME TO bets"))
  op.execute(sa.text("CREATE INDEX ix_bets_poker_id ON bets (poker_id)"))
  op.execute(sa.text("CREATE INDEX ix_bets_better_id ON bets (better_id)"))
  op.execute(sa.text("CREATE INDEX ix_bets_date ON bets (date)"))
