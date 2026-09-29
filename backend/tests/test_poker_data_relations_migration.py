import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).parents[1]
PREVIOUS_HEAD = "f6a8b2c4d9e1"


def _env(database: Path) -> dict[str, str]:
  return os.environ | {
    "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    "DEBUG": "false",
  }


def _upgrade(database: Path, revision: str, *, check: bool = True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", "upgrade", revision],
    cwd=BACKEND_ROOT,
    env=_env(database),
    check=check,
    capture_output=True,
    text=True,
  )


def _legacy_rows(connection: sqlite3.Connection):
  user_id = connection.execute(
    "INSERT INTO users (telegram_id, name, is_admin, is_approved) "
    "VALUES (101, 'Player', 0, 1) RETURNING row_id"
  ).fetchone()[0]
  params_id = connection.execute(
    "INSERT INTO poker_params "
    "(buyin_size_chips, buyin_size_kopecks, bb_size_chips, max_buyins) "
    "VALUES (200, 20000, 10, 3) RETURNING row_id"
  ).fetchone()[0]
  poker_id = connection.execute(
    "INSERT INTO pokers (params_id, date) VALUES (?, '2026-09-29') RETURNING row_id",
    (params_id,),
  ).fetchone()[0]
  has_poker_id = "poker_id" in {
    row[1] for row in connection.execute("PRAGMA table_info('poker_data')")
  }
  identity_columns = "poker_id, " if has_poker_id else ""
  identity_values = "?, " if has_poker_id else ""
  identity_args = (poker_id, user_id) if has_poker_id else (user_id,)
  connection.execute(
    "INSERT INTO poker_data "
    f"({identity_columns}date, player_name, player_id, is_prev_winner, buyins, "
    "big_buyin_count, super_buyin_count, chips, money_kopecks) "
    f"VALUES ({identity_values}'2026-09-29', 'Historical Player', ?, 0, 2, 1, 0, "
    "NULL, -12345)",
    identity_args,
  )
  second_user = connection.execute(
    "INSERT INTO users (telegram_id, name, is_admin, is_approved) "
    "VALUES (102, 'Zero Chips', 0, 1) RETURNING row_id"
  ).fetchone()[0]
  identity_args = (poker_id, second_user) if has_poker_id else (second_user,)
  connection.execute(
    "INSERT INTO poker_data "
    f"({identity_columns}date, player_name, player_id, is_prev_winner, buyins, "
    "big_buyin_count, super_buyin_count, chips, money_kopecks) "
    f"VALUES ({identity_values}'2026-09-29', 'Zero Chips', ?, 0, 1, 0, 0, 0, 67890)",
    identity_args,
  )
  connection.commit()
  return poker_id, user_id, second_user


def test_populated_upgrade_backfills_ids_and_preserves_business_values(tmp_path):
  database = tmp_path / "populated.db"
  _upgrade(database, PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    poker_id, user_id, second_user = _legacy_rows(connection)
    before = connection.execute(
      "SELECT row_id, date, player_name, player_id, chips, money_kopecks, "
      "created_at, updated_at FROM poker_data ORDER BY row_id"
    ).fetchall()

  _upgrade(database, "head")

  with sqlite3.connect(database) as connection:
    after = connection.execute(
      "SELECT row_id, date, player_name, player_id, chips, money_kopecks, "
      "created_at, updated_at FROM poker_data ORDER BY row_id"
    ).fetchall()
    identities = connection.execute(
      "SELECT poker_id, player_id FROM poker_data ORDER BY row_id"
    ).fetchall()
    assert after == before
    assert identities == [(poker_id, user_id), (poker_id, second_user)]
    assert [row[4] for row in after] == [None, 0]
    assert sum(row[5] for row in after) == 55_545
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
  ("kind", "message"),
  [
    ("unmatched_date", "has no matching Poker"),
    ("orphan_player", "has no matching User"),
  ],
)
def test_invalid_legacy_relation_refuses_migration_safely(tmp_path, kind, message):
  database = tmp_path / f"{kind}.db"
  _upgrade(database, PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    _, user_id, _ = _legacy_rows(connection)
    connection.execute("DELETE FROM poker_data")
    date = "2026-09-30" if kind == "unmatched_date" else "2026-09-29"
    player_id = user_id if kind == "unmatched_date" else 999_999
    connection.execute(
      "INSERT INTO poker_data (date, player_name, player_id) VALUES (?, 'Bad', ?)",
      (date, player_id),
    )
    connection.commit()

  result = _upgrade(database, "head", check=False)

  assert result.returncode != 0
  assert message in result.stderr
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT COUNT(*) FROM poker_data").fetchone() == (1,)
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
      PREVIOUS_HEAD,
    )
    assert "poker_id" not in {
      row[1] for row in connection.execute("PRAGMA table_info('poker_data')")
    }


def test_duplicate_target_identity_preflight_is_defensive(tmp_path):
  database = tmp_path / "duplicate.db"
  _upgrade(database, PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    poker_id, user_id, _ = _legacy_rows(connection)
    connection.execute("DELETE FROM poker_data")
    connection.execute("ALTER TABLE poker_data RENAME TO poker_data_constrained")
    connection.execute(
      "CREATE TABLE poker_data AS SELECT * FROM poker_data_constrained WHERE 0"
    )
    connection.execute("DROP TABLE poker_data_constrained")
    for row_id, name in enumerate(("One", "Two"), start=1):
      connection.execute(
        "INSERT INTO poker_data (row_id, date, player_name, player_id, is_prev_winner, buyins, "
        "big_buyin_count, super_buyin_count, chips, money_kopecks, created_at, updated_at) "
        "VALUES (?, '2026-09-29', ?, ?, 0, 0, 0, 0, NULL, 0, "
        "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (row_id, name, user_id),
      )
    connection.commit()
    assert poker_id > 0

  result = _upgrade(database, "head", check=False)
  assert result.returncode != 0
  assert "duplicate target identity" in result.stderr
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT COUNT(*) FROM poker_data").fetchone() == (2,)


def test_new_constraints_reject_invalid_relations_duplicates_and_deletes(tmp_path):
  database = tmp_path / "constraints.db"
  _upgrade(database, "head")
  with sqlite3.connect(database) as connection:
    connection.execute("PRAGMA foreign_keys=ON")
    poker_id, user_id, _ = _legacy_rows(connection)
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute(
        "INSERT INTO poker_data (poker_id, date, player_name, player_id) "
        "VALUES (999999, '2026-09-30', 'Bad Poker', ?)",
        (user_id,),
      )
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute(
        "INSERT INTO poker_data (poker_id, date, player_name, player_id) "
        "VALUES (?, '2026-09-29', 'Bad User', 999999)",
        (poker_id,),
      )
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute(
        "INSERT INTO poker_data (poker_id, date, player_name, player_id) "
        "VALUES (?, '2026-09-29', 'Duplicate', ?)",
        (poker_id, user_id),
      )
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute("DELETE FROM pokers WHERE row_id = ?", (poker_id,))
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute("DELETE FROM users WHERE row_id = ?", (user_id,))


def test_downgrade_preserves_legacy_business_rows(tmp_path):
  database = tmp_path / "downgrade.db"
  _upgrade(database, PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    _legacy_rows(connection)
    before = connection.execute(
      "SELECT date, player_name, player_id, chips, money_kopecks FROM poker_data ORDER BY row_id"
    ).fetchall()
  _upgrade(database, "head")
  subprocess.run(
    [sys.executable, "-m", "alembic", "downgrade", PREVIOUS_HEAD],
    cwd=BACKEND_ROOT,
    env=_env(database),
    check=True,
    capture_output=True,
    text=True,
  )
  with sqlite3.connect(database) as connection:
    after = connection.execute(
      "SELECT date, player_name, player_id, chips, money_kopecks FROM poker_data ORDER BY row_id"
    ).fetchall()
    assert after == before
    assert "poker_id" not in {
      row[1] for row in connection.execute("PRAGMA table_info('poker_data')")
    }
