import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).parents[1]
PREVIOUS_HEAD = "a1c3e5f7b9d2"


def _env(database: Path) -> dict[str, str]:
  return os.environ | {
    "DATABASE_URL": f"sqlite+aiosqlite:///{database}",
    "DEBUG": "false",
  }


def _alembic(database: Path, *arguments: str, check: bool = True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", *arguments],
    cwd=BACKEND_ROOT,
    env=_env(database),
    check=check,
    capture_output=True,
    text=True,
  )


def _seed_relations(connection: sqlite3.Connection):
  user_id = connection.execute(
    "INSERT INTO users (telegram_id, name, is_admin, is_approved) "
    "VALUES (301, 'Player', 0, 1) RETURNING row_id"
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
  return poker_id, user_id


def _insert_event(
  connection: sqlite3.Connection,
  *,
  poker_id: int,
  player_id: int,
  operation_id: str | None,
  count: int,
):
  has_poker_id = "poker_id" in {
    row[1] for row in connection.execute("PRAGMA table_info('buyins_data')")
  }
  columns = "poker_id, " if has_poker_id else ""
  values = "?, " if has_poker_id else ""
  arguments = (
    (poker_id, player_id, operation_id, count)
    if has_poker_id
    else (player_id, operation_id, count)
  )
  connection.execute(
    f"INSERT INTO buyins_data ({columns}date, player_id, player_name, operation_id, buyin, "
    f"created_at, updated_at) VALUES ({values}'2026-09-29', ?, 'Historical Name', ?, ?, "
    "'2026-09-29 10:00:00', '2026-09-29 10:05:00')",
    arguments,
  )


def test_populated_upgrade_preserves_events_and_backfills_poker_id(tmp_path):
  database = tmp_path / "populated.db"
  _alembic(database, "upgrade", PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    poker_id, user_id = _seed_relations(connection)
    _insert_event(
      connection, poker_id=poker_id, player_id=user_id, operation_id="op-1", count=1
    )
    _insert_event(
      connection, poker_id=poker_id, player_id=user_id, operation_id=None, count=2
    )
    connection.commit()
    before = connection.execute(
      "SELECT row_id, date, player_id, player_name, buyin, operation_id, created_at, updated_at "
      "FROM buyins_data ORDER BY row_id"
    ).fetchall()

  _alembic(database, "upgrade", "head")

  with sqlite3.connect(database) as connection:
    after = connection.execute(
      "SELECT row_id, date, player_id, player_name, buyin, operation_id, created_at, updated_at "
      "FROM buyins_data ORDER BY row_id"
    ).fetchall()
    assert after == before
    assert connection.execute(
      "SELECT poker_id FROM buyins_data ORDER BY row_id"
    ).fetchall() == [(poker_id,), (poker_id,)]
    assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
    with pytest.raises(sqlite3.IntegrityError):
      _insert_event(
        connection, poker_id=poker_id, player_id=user_id, operation_id="op-1", count=3
      )


@pytest.mark.parametrize(
  ("kind", "message"),
  [
    ("unmatched", "has no matching Poker"),
    ("orphan", "has no matching User"),
  ],
)
def test_invalid_legacy_relation_refuses_before_rebuild(tmp_path, kind, message):
  database = tmp_path / f"{kind}.db"
  _alembic(database, "upgrade", PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    poker_id, user_id = _seed_relations(connection)
    if kind == "unmatched":
      connection.execute(
        "INSERT INTO buyins_data (date, player_id, player_name, buyin, created_at, updated_at) "
        "VALUES ('2026-09-30', ?, 'Bad', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)",
        (user_id,),
      )
    else:
      connection.execute(
        "INSERT INTO buyins_data (date, player_id, player_name, buyin, created_at, updated_at) "
        "VALUES ('2026-09-29', 999999, 'Bad', 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)"
      )
    connection.commit()
    assert poker_id > 0

  result = _alembic(database, "upgrade", "head", check=False)
  assert result.returncode != 0
  assert message in result.stderr
  with sqlite3.connect(database) as connection:
    assert connection.execute("SELECT COUNT(*) FROM buyins_data").fetchone() == (1,)
    assert "poker_id" not in {
      row[1] for row in connection.execute("PRAGMA table_info('buyins_data')")
    }
    assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
      PREVIOUS_HEAD,
    )


def test_constraints_restrict_invalid_relations_and_allow_multiple_events(tmp_path):
  database = tmp_path / "constraints.db"
  _alembic(database, "upgrade", "head")
  with sqlite3.connect(database) as connection:
    connection.execute("PRAGMA foreign_keys=ON")
    poker_id, user_id = _seed_relations(connection)
    _insert_event(
      connection, poker_id=poker_id, player_id=user_id, operation_id="one", count=1
    )
    _insert_event(
      connection, poker_id=poker_id, player_id=user_id, operation_id="two", count=1
    )
    assert connection.execute("SELECT COUNT(*) FROM buyins_data").fetchone() == (2,)
    with pytest.raises(sqlite3.IntegrityError):
      _insert_event(
        connection, poker_id=999999, player_id=user_id, operation_id="bad-poker", count=1
      )
    with pytest.raises(sqlite3.IntegrityError):
      _insert_event(
        connection, poker_id=poker_id, player_id=999999, operation_id="bad-user", count=1
      )
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute("DELETE FROM pokers WHERE row_id = ?", (poker_id,))
    with pytest.raises(sqlite3.IntegrityError):
      connection.execute("DELETE FROM users WHERE row_id = ?", (user_id,))


def test_downgrade_preserves_historical_events(tmp_path):
  database = tmp_path / "downgrade.db"
  _alembic(database, "upgrade", PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    poker_id, user_id = _seed_relations(connection)
    _insert_event(
      connection, poker_id=poker_id, player_id=user_id, operation_id="keep", count=4
    )
    connection.commit()
    before = connection.execute(
      "SELECT date, player_id, player_name, buyin, operation_id, created_at, updated_at "
      "FROM buyins_data"
    ).fetchall()
  _alembic(database, "upgrade", "head")
  _alembic(database, "downgrade", PREVIOUS_HEAD)
  with sqlite3.connect(database) as connection:
    after = connection.execute(
      "SELECT date, player_id, player_name, buyin, operation_id, created_at, updated_at "
      "FROM buyins_data"
    ).fetchall()
    assert after == before
    assert "poker_id" not in {
      row[1] for row in connection.execute("PRAGMA table_info('buyins_data')")
    }
