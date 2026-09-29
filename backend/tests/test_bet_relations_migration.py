import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PREVIOUS = "b2d4f6a8c1e3"


def _run(db, *args, check=True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", *args], cwd=ROOT,
    env=os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}", "DEBUG": "false"},
    check=check, capture_output=True, text=True,
  )


def _relations(c):
  user = c.execute("INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(501,'Bettor',0,1) RETURNING row_id").fetchone()[0]
  winner = c.execute("INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(502,'Winner',0,1) RETURNING row_id").fetchone()[0]
  loser = c.execute("INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(503,'Loser',0,1) RETURNING row_id").fetchone()[0]
  pp = c.execute("INSERT INTO poker_params(buyin_size_chips,buyin_size_kopecks,bb_size_chips,max_buyins) VALUES(200,20000,10,3) RETURNING row_id").fetchone()[0]
  poker = c.execute("INSERT INTO pokers(params_id,date) VALUES(?,'2026-09-29') RETURNING row_id", (pp,)).fetchone()[0]
  c.execute("INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) VALUES(?, '2026-09-29', ?, 'Winner', 1, 10000)", (poker, winner))
  c.execute("INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) VALUES(?, '2026-09-29', ?, 'Loser', 1, -10000)", (poker, loser))
  bp = c.execute("INSERT INTO bet_params(small_size_kopecks,small_score,small_score_combo,big_size_kopecks,big_score,big_score_combo) VALUES(10000,1,2,20000,2,4) RETURNING row_id").fetchone()[0]
  return poker, user, bp


def _bet(c, poker, user, params, *, operation="normal"):
  table_columns = {r[1] for r in c.execute("PRAGMA table_info('bets')")}
  has = "poker_id" in table_columns
  columns, values, prefix = ("poker_id,", "?,", (poker,)) if has else ("", "", ())
  if "winner_id" in table_columns:
    winner = c.execute("SELECT row_id FROM users WHERE name='Winner'").fetchone()[0]
    loser = c.execute("SELECT row_id FROM users WHERE name='Loser'").fetchone()[0]
    columns += "winner_id,loser_id,"
    values += "?,?,"
    prefix += (winner, loser)
  date = "2026-09-30" if operation == "bad-date" else "2026-09-29"
  better = 999999 if operation == "bad-user" else user
  param = 999999 if operation == "bad-param" else params
  c.execute(
    f"INSERT INTO bets({columns}params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid,created_at,updated_at) "
    f"VALUES({values}?,?, 'Bettor',?,12345,'Winner','Loser',7,1,'2026-09-29 10:00:00','2026-09-29 10:05:00')",
    prefix + (param, date, better),
  )


def _remove_legacy_bet_unique(c):
  c.execute("ALTER TABLE bets RENAME TO bets_with_unique")
  c.execute(
    """CREATE TABLE bets (
      row_id INTEGER PRIMARY KEY AUTOINCREMENT,
      params_id INTEGER,
      date DATE,
      better_name VARCHAR(255) NOT NULL,
      better_id INTEGER NOT NULL,
      size_kopecks INTEGER NOT NULL,
      winner VARCHAR(255),
      looser VARCHAR(255),
      score INTEGER DEFAULT 0 NOT NULL,
      is_paid BOOLEAN DEFAULT 0 NOT NULL,
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
      updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL
    )"""
  )
  c.execute("DROP TABLE bets_with_unique")


def test_populated_upgrade_preserves_bet_and_backfills(tmp_path):
  db = tmp_path / "populated.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, user, params = _relations(c)
    _bet(c, poker, user, params)
    c.commit()
    before = c.execute("SELECT params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid,created_at,updated_at FROM bets").fetchall()
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    after = c.execute("SELECT params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid,created_at,updated_at FROM bets").fetchall()
    assert after == before
    assert c.execute("SELECT poker_id FROM bets").fetchone() == (poker,)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(("kind", "message"), [
  ("bad-date", "no matching Poker"), ("bad-user", "no matching User"),
  ("bad-param", "no matching BetParam"),
])
def test_invalid_legacy_bet_refuses_safely(tmp_path, kind, message):
  db = tmp_path / f"{kind}.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, user, params = _relations(c)
    _bet(c, poker, user, params, operation=kind)
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and message in result.stderr
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT COUNT(*) FROM bets").fetchone() == (1,)
    assert "poker_id" not in {r[1] for r in c.execute("PRAGMA table_info('bets')")}
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)


def test_ambiguous_poker_date_refuses_before_schema_change(tmp_path):
  db = tmp_path / "ambiguous-date.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, user, params = _relations(c)
    poker_params = c.execute("SELECT params_id FROM pokers WHERE row_id=?", (poker,)).fetchone()[0]
    c.execute("DROP INDEX uq_pokers_date")
    c.execute("INSERT INTO pokers(params_id,date) VALUES(?,'2026-09-29')", (poker_params,))
    _bet(c, poker, user, params)
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and "matches 2 Poker rows" in result.stderr
  with sqlite3.connect(db) as c:
    assert "poker_id" not in {r[1] for r in c.execute("PRAGMA table_info('bets')")}
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)


def test_duplicate_target_identity_refuses_before_schema_change(tmp_path):
  db = tmp_path / "duplicate-target.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, user, params = _relations(c)
    _remove_legacy_bet_unique(c)
    _bet(c, poker, user, params)
    _bet(c, poker, user, params)
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and "duplicate target identity" in result.stderr
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT COUNT(*) FROM bets").fetchone() == (2,)
    assert "poker_id" not in {r[1] for r in c.execute("PRAGMA table_info('bets')")}
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)


def test_constraints_and_delete_restrictions(tmp_path):
  db = tmp_path / "constraints.db"
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    c.execute("PRAGMA foreign_keys=ON")
    poker, user, params = _relations(c)
    _bet(c, poker, user, params)
    with pytest.raises(sqlite3.IntegrityError):
      _bet(c, 999999, user, params)
    with pytest.raises(sqlite3.IntegrityError):
      _bet(c, poker, 999999, params)
    with pytest.raises(sqlite3.IntegrityError):
      _bet(c, poker, user, 999999)
    with pytest.raises(sqlite3.IntegrityError):
      _bet(c, poker, user, params)
    for table, row_id in (("pokers", poker), ("users", user), ("bet_params", params)):
      with pytest.raises(sqlite3.IntegrityError):
        c.execute(f"DELETE FROM {table} WHERE row_id=?", (row_id,))


def test_downgrade_preserves_bet_rows(tmp_path):
  db = tmp_path / "down.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, user, params = _relations(c)
    _bet(c, poker, user, params)
    c.commit()
    before = c.execute("SELECT * FROM bets").fetchall()
  _run(db, "upgrade", "head")
  _run(db, "downgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT * FROM bets").fetchall() == before
