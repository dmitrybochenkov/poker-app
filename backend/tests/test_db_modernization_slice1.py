import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).parents[1]
PREVIOUS_HEAD = "e5b7c9d1f3a2"
PRODUCTION_REVISION = "c8f4e1a2b7d9"


def _environment(database: Path) -> dict[str, str]:
  return os.environ | {
    "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    "DEBUG": "false",
  }


def _upgrade(database: Path, revision: str, *, check: bool = True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", revision],
    cwd=BACKEND_ROOT,
    env=_environment(database),
    check=check,
    capture_output=True,
    text=True,
  )


def _seed_poker(connection: sqlite3.Connection, *, poker_date: str) -> None:
  params_id = connection.execute(
    "INSERT INTO poker_params "
    "(buyin_size_chips, buyin_size_kopecks, bb_size_chips, max_buyins) "
    "VALUES (200, 20000, 10, 3) RETURNING row_id"
  ).fetchone()[0]
  connection.execute(
    "INSERT INTO pokers (params_id, date) VALUES (?, ?)",
    (params_id, poker_date),
  )


def test_application_connections_enable_foreign_keys(tmp_path):
  database = tmp_path / "application.db"
  script = """
import asyncio
from sqlalchemy import text
from app.db.session import engine

async def main():
  async with engine.connect() as connection:
    print(await connection.scalar(text("PRAGMA foreign_keys")))
  await engine.dispose()

asyncio.run(main())
"""
  result = subprocess.run(
    [sys.executable, "-c", script],
    cwd=BACKEND_ROOT,
    env=_environment(database),
    check=True,
    capture_output=True,
    text=True,
  )
  assert result.stdout.strip().splitlines()[-1] == "1"


def test_current_head_foreign_keys_are_enforced_with_existing_delete_semantics(tmp_path):
  database = tmp_path / "foreign-keys.db"
  _upgrade(database, "head")

  with sqlite3.connect(database) as connection:
    connection.execute("PRAGMA foreign_keys=ON")
    assert connection.execute("PRAGMA foreign_keys").fetchone() == (1,)

    _seed_poker(connection, poker_date="2026-09-29")
    params_id, poker_id = connection.execute(
      "SELECT params_id, row_id FROM pokers"
    ).fetchone()
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute("DELETE FROM poker_params WHERE row_id = ?", (params_id,))

    user_id = connection.execute(
      "INSERT INTO users (telegram_id, name, is_admin, is_approved) "
      "VALUES (1001, 'VK User', 0, 1) RETURNING row_id"
    ).fetchone()[0]
    connection.execute(
      "INSERT INTO vk_conversation_states "
      "(vk_user_id, user_row_id, state_type, payload, updated_at) "
      "VALUES (2001, ?, 'test', '{}', CURRENT_TIMESTAMP)",
      (user_id,),
    )
    connection.execute("DELETE FROM users WHERE row_id = ?", (user_id,))
    assert connection.execute(
      "SELECT COUNT(*) FROM vk_conversation_states WHERE vk_user_id = 2001"
    ).fetchone() == (0,)

    bettor_id = connection.execute(
      "INSERT INTO users (telegram_id, name, is_admin, is_approved) "
      "VALUES (1002, 'Player', 0, 1) RETURNING row_id"
    ).fetchone()[0]
    bet_params_id = connection.execute(
      "INSERT INTO bet_params "
      "(small_size_kopecks, small_score, small_score_combo, "
      "big_size_kopecks, big_score, big_score_combo) "
      "VALUES (10000, 1, 2, 20000, 2, 4) RETURNING row_id"
    ).fetchone()[0]
    bet_id = connection.execute(
      "INSERT INTO bets "
      "(poker_id, params_id, date, better_name, better_id, size_kopecks, score, is_paid) "
      "VALUES (?, ?, '2026-09-29', 'Player', ?, 10000, 0, 0) RETURNING row_id",
      (poker_id, bet_params_id, bettor_id),
    ).fetchone()[0]
    receipt_id = connection.execute(
      "INSERT INTO bet_payment_receipts (user_row_id, platform, status) "
      "VALUES (7, 'tg', 'manual') RETURNING row_id"
    ).fetchone()[0]
    connection.execute(
      "INSERT INTO bet_payment_receipt_bets (receipt_id, bet_id) VALUES (?, ?)",
      (receipt_id, bet_id),
    )
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute(
        "INSERT INTO bet_payment_receipt_bets (receipt_id, bet_id) VALUES (?, ?)",
        (receipt_id, 999_999),
      )
    connection.execute("DELETE FROM bets WHERE row_id = ?", (bet_id,))
    assert connection.execute(
      "SELECT COUNT(*) FROM bet_payment_receipt_bets WHERE receipt_id = ?",
      (receipt_id,),
    ).fetchone() == (0,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    assert poker_id > 0


@pytest.mark.parametrize("starting_revision", [None, PREVIOUS_HEAD, PRODUCTION_REVISION])
def test_upgrade_paths_enforce_unique_poker_date(tmp_path, starting_revision):
  label = starting_revision or "fresh"
  database = tmp_path / f"upgrade-{label}.db"
  if starting_revision is not None:
    _upgrade(database, starting_revision)
  _upgrade(database, "head")

  with sqlite3.connect(database) as connection:
    _seed_poker(connection, poker_date="2026-09-29")
    with pytest.raises(sqlite3.IntegrityError):
      _seed_poker(connection, poker_date="2026-09-29")
    _seed_poker(connection, poker_date="2026-09-30")
    connection.commit()
    assert connection.execute("SELECT COUNT(*) FROM pokers").fetchone() == (2,)
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


def test_duplicate_poker_dates_refuse_migration_without_changing_data(tmp_path):
  database = tmp_path / "duplicate-date.db"
  _upgrade(database, PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    _seed_poker(connection, poker_date="2026-09-29")
    _seed_poker(connection, poker_date="2026-09-29")
    connection.commit()

  result = _upgrade(database, "head", check=False)

  assert result.returncode != 0
  assert "Cannot enforce uq_pokers_date" in result.stderr
  assert "Resolve the duplicate game rows" in result.stderr
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT COUNT(*) FROM pokers").fetchone() == (2,)
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
      PREVIOUS_HEAD,
    )
    assert connection.execute(
      "SELECT COUNT(*) FROM sqlite_master "
      "WHERE type = 'index' AND name = 'uq_pokers_date'"
    ).fetchone() == (0,)
