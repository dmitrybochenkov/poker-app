import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]
PREVIOUS = "d4f6a8c1e3b5"


def _run(db, *args, check=True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", *args], cwd=ROOT,
    env=os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}", "DEBUG": "false"},
    check=check, capture_output=True, text=True,
  )


def _seed_base(c):
  users = {}
  for external_id, name in enumerate(("Admin", "A", "B", "C", "D"), start=801):
    users[name] = c.execute(
      "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(?,?,0,1) RETURNING row_id",
      (external_id, name),
    ).fetchone()[0]
  poker_param = c.execute(
    "INSERT INTO poker_params(buyin_size_chips,buyin_size_kopecks,bb_size_chips,max_buyins) "
    "VALUES(200,20000,10,3) RETURNING row_id"
  ).fetchone()[0]
  bet_param = c.execute(
    "INSERT INTO bet_params(small_size_kopecks,small_score,small_score_combo,"
    "big_size_kopecks,big_score,big_score_combo) VALUES(10000,1,2,20000,2,4) RETURNING row_id"
  ).fetchone()[0]
  tournament_param = c.execute(
    "INSERT INTO bet_tournament_params(tournament_type,bet_param_id,percent_to_first,"
    "percent_to_second,percent_to_third,duration_months) VALUES('regular',?,50,33,17,4) RETURNING row_id",
    (bet_param,),
  ).fetchone()[0]
  return users, poker_param, bet_param, tournament_param


def _add_bet(c, *, date_value, poker_param, bet_param, user_id, name, score):
  poker_id = c.execute(
    "INSERT INTO pokers(params_id,date) VALUES(?,?) RETURNING row_id", (poker_param, date_value)
  ).fetchone()[0]
  c.execute(
    "INSERT INTO bets(poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,"
    "winner_id,loser_id,score,is_paid) VALUES(?,?,?, ?,?,10000,'A','B',?,?,?,1)",
    (poker_id, bet_param, date_value, name, user_id, user_id, user_id, score),
  )


def _add_tournament(c, *, params_id, start, end, bank, first, second, third, paid=1):
  return c.execute(
    "INSERT INTO bet_tournaments(params_id,start_date,end_date,current_bank_size_kopecks,"
    "first_place_name,second_place_name,third_place_name,is_paid,tournament_type) "
    "VALUES(?,?,?,?,?,?,?,?, 'regular') RETURNING row_id",
    (params_id, start, end, bank, first, second, third, paid),
  ).fetchone()[0]


def test_historical_backfill_matches_frozen_tie_and_floor_semantics(tmp_path):
  db = tmp_path / "historical.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    for day, name, score in (("2025-04-01", "A", 7), ("2025-04-02", "B", 7), ("2025-04-03", "C", 6)):
      _add_bet(c, date_value=day, poker_param=poker_param, bet_param=bet_param, user_id=users[name], name=name, score=score)
    first = _add_tournament(c, params_id=tournament_param, start="2025-04-01", end="2025-04-30", bank=832000, first="A, B", second="A, B", third="C")
    for day, name in (("2026-01-01", "A"), ("2026-01-02", "B"), ("2026-01-03", "C")):
      _add_bet(c, date_value=day, poker_param=poker_param, bet_param=bet_param, user_id=users[name], name=name, score=2)
    second = _add_tournament(c, params_id=tournament_param, start="2026-01-01", end="2026-01-31", bank=784000, first="C, B, A", second="A, B, C", third="B, A, C")
    c.commit()
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    rows = c.execute(
      "SELECT tournament_id,user_id,position,score,payout_kopecks,name_snapshot "
      "FROM bet_tournament_results ORDER BY tournament_id,user_id"
    ).fetchall()
    assert rows[:3] == [
      (first, users["A"], 1, 7, 345280, "A"),
      (first, users["B"], 1, 7, 345280, "B"),
      (first, users["C"], 3, 6, 141440, "C"),
    ]
    assert rows[3:] == [
      (second, users["A"], 1, 2, 261333, "A"),
      (second, users["B"], 1, 2, 261333, "B"),
      (second, users["C"], 1, 2, 261333, "C"),
    ]
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
  ("damage", "message"),
  [
    ("interval", "invalid date interval"),
    ("params", "parameter row is missing"),
    ("orphan", "orphan canonical bettor"),
    ("comma", "comma-ambiguous"),
    ("membership", "membership is inconsistent"),
    ("bank", "bank must be nonnegative"),
  ],
)
def test_invalid_historical_result_refuses_before_table_creation(tmp_path, damage, message):
  db = tmp_path / f"invalid-{damage}.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    name = "A, Alias" if damage == "comma" else "A"
    _add_bet(c, date_value="2025-04-01", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name=name, score=3)
    _add_tournament(
      c, params_id=999999 if damage == "params" else tournament_param,
      start="2025-04-30" if damage == "interval" else "2025-04-01",
      end="2025-04-01" if damage == "interval" else "2025-04-30",
      bank=-1 if damage == "bank" else 100,
      first="Wrong" if damage == "membership" else name, second="", third="",
    )
    if damage == "orphan":
      c.execute("PRAGMA foreign_keys=OFF")
      c.execute("UPDATE bets SET better_id=999999")
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and message in result.stderr
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)
    assert c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='bet_tournament_results'").fetchone() is None


def test_downgrade_drops_results_and_preserves_legacy_tournament(tmp_path):
  db = tmp_path / "downgrade.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    _add_bet(c, date_value="2025-04-01", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name="A", score=3)
    tournament = _add_tournament(c, params_id=tournament_param, start="2025-04-01", end="2025-04-30", bank=100, first="A", second="", third="")
    before = c.execute("SELECT * FROM bet_tournaments WHERE row_id=?", (tournament,)).fetchone()
    c.commit()
  _run(db, "upgrade", "head")
  _run(db, "downgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT * FROM bet_tournaments WHERE row_id=?", (tournament,)).fetchone() == before
    assert c.execute("SELECT name FROM sqlite_master WHERE name='bet_tournament_results'").fetchone() is None


def test_backfill_uses_latest_snapshot_and_keeps_duplicate_names_canonical(tmp_path):
  db = tmp_path / "names.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    _add_bet(c, date_value="2025-01-01", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name="Old", score=2)
    _add_bet(c, date_value="2025-01-02", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name="Shared", score=2)
    _add_bet(c, date_value="2025-01-03", poker_param=poker_param, bet_param=bet_param, user_id=users["B"], name="Shared", score=4)
    _add_tournament(c, params_id=tournament_param, start="2025-01-01", end="2025-01-31", bank=100, first="Shared, Shared", second="Shared, Shared", third="")
    c.commit()
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    assert c.execute(
      "SELECT user_id,position,score,payout_kopecks,name_snapshot FROM bet_tournament_results ORDER BY user_id"
    ).fetchall() == [
      (users["A"], 1, 4, 41, "Shared"),
      (users["B"], 1, 4, 41, "Shared"),
    ]


def test_result_constraints_and_delete_restrictions(tmp_path):
  db = tmp_path / "constraints.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    _add_bet(c, date_value="2025-04-01", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name="A", score=3)
    tournament = _add_tournament(c, params_id=tournament_param, start="2025-04-01", end="2025-04-30", bank=100, first="A", second="", third="")
    c.commit()
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    c.execute("PRAGMA foreign_keys=ON")
    base = (tournament, users["B"], 2, 1, 1, "B")
    for values in (
      (999999, users["B"], 2, 1, 1, "B"),
      (tournament, 999999, 2, 1, 1, "B"),
      (tournament, users["B"], 4, 1, 1, "B"),
      (tournament, users["B"], 2, 1, -1, "B"),
    ):
      with pytest.raises(sqlite3.IntegrityError):
        c.execute(
          "INSERT INTO bet_tournament_results(tournament_id,user_id,position,score,payout_kopecks,name_snapshot) VALUES(?,?,?,?,?,?)",
          values,
        )
    c.execute(
      "INSERT INTO bet_tournament_results(tournament_id,user_id,position,score,payout_kopecks,name_snapshot) VALUES(?,?,?,?,?,?)",
      base,
    )
    with pytest.raises(sqlite3.IntegrityError):
      c.execute(
        "INSERT INTO bet_tournament_results(tournament_id,user_id,position,score,payout_kopecks,name_snapshot) VALUES(?,?,?,?,?,?)",
        base,
      )
    for table, row_id in (("bet_tournaments", tournament), ("users", users["B"])):
      with pytest.raises(sqlite3.IntegrityError):
        c.execute(f"DELETE FROM {table} WHERE row_id=?", (row_id,))


def test_ambiguous_duplicate_legacy_name_refuses_migration(tmp_path):
  db = tmp_path / "ambiguous-name.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    users, poker_param, bet_param, tournament_param = _seed_base(c)
    _add_bet(c, date_value="2025-01-01", poker_param=poker_param, bet_param=bet_param, user_id=users["A"], name="Shared", score=3)
    _add_bet(c, date_value="2025-01-02", poker_param=poker_param, bet_param=bet_param, user_id=users["B"], name="Shared", score=2)
    _add_tournament(c, params_id=tournament_param, start="2025-01-01", end="2025-01-31", bank=100, first="Shared", second="Shared", third="")
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and "is ambiguous" in result.stderr
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)
    assert c.execute("SELECT name FROM sqlite_master WHERE name='bet_tournament_results'").fetchone() is None
