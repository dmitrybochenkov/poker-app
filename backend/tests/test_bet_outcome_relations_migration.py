import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
PREVIOUS = "c3e5f7a9b2d4"


def _run(db, *args, check=True):
  return subprocess.run(
    [sys.executable, "-m", "alembic", *args], cwd=ROOT,
    env=os.environ | {"DATABASE_URL": f"sqlite+aiosqlite:///{db}", "DEBUG": "false"},
    check=check, capture_output=True, text=True,
  )


def _seed_relations(c, *, duplicate_winner=False):
  bettor = c.execute(
    "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(701,'Bettor',0,1) RETURNING row_id"
  ).fetchone()[0]
  winner = c.execute(
    "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(702,'Winner',0,1) RETURNING row_id"
  ).fetchone()[0]
  loser = c.execute(
    "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(703,'Loser',0,1) RETURNING row_id"
  ).fetchone()[0]
  pp = c.execute(
    "INSERT INTO poker_params(buyin_size_chips,buyin_size_kopecks,bb_size_chips,max_buyins) "
    "VALUES(200,20000,10,3) RETURNING row_id"
  ).fetchone()[0]
  poker = c.execute(
    "INSERT INTO pokers(params_id,date) VALUES(?,'2026-09-29') RETURNING row_id", (pp,)
  ).fetchone()[0]
  bp = c.execute(
    "INSERT INTO bet_params(small_size_kopecks,small_score,small_score_combo,"
    "big_size_kopecks,big_score,big_score_combo) VALUES(10000,1,2,20000,2,4) RETURNING row_id"
  ).fetchone()[0]
  c.execute(
    "INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) "
    "VALUES(?,'2026-09-29',?,'Winner',1,10000)", (poker, winner),
  )
  c.execute(
    "INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) "
    "VALUES(?,'2026-09-29',?,'Loser',1,-10000)", (poker, loser),
  )
  if duplicate_winner:
    duplicate = c.execute(
      "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(704,'Winner',0,1) RETURNING row_id"
    ).fetchone()[0]
    c.execute(
      "INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) "
      "VALUES(?,'2026-09-29',?,'Winner',1,0)", (poker, duplicate),
    )
  return poker, bettor, winner, loser, bp


def _insert_legacy_bet(c, poker, bettor, params, *, winner="Winner", loser="Loser"):
  return c.execute(
    "INSERT INTO bets(poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,"
    "score,is_paid,created_at,updated_at) VALUES(?,?,'2026-09-29','Bettor',?,12345,?,?,7,1,"
    "'2026-09-29 10:00:00','2026-09-29 10:05:00') RETURNING row_id",
    (poker, params, bettor, winner, loser),
  ).fetchone()[0]


def test_upgrade_backfills_participant_ids_and_preserves_snapshots(tmp_path):
  db = tmp_path / "populated.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, bettor, winner, loser, params = _seed_relations(c)
    bet_id = _insert_legacy_bet(c, poker, bettor, params)
    receipt_id = c.execute(
      "INSERT INTO bet_payment_receipts(user_row_id,platform,status) "
      "VALUES(?,'tg','manual') RETURNING row_id", (bettor,),
    ).fetchone()[0]
    c.execute(
      "INSERT INTO bet_payment_receipt_bets(receipt_id,bet_id) VALUES(?,?)",
      (receipt_id, bet_id),
    )
    equal_id = c.execute(
      "INSERT INTO pokers(params_id,date) SELECT params_id,'2026-09-30' FROM pokers WHERE row_id=? RETURNING row_id",
      (poker,),
    ).fetchone()[0]
    c.execute(
      "INSERT INTO poker_data(poker_id,date,player_id,player_name,buyins,money_kopecks) "
      "VALUES(?,'2026-09-30',?,'Winner',1,0)", (equal_id, winner),
    )
    c.execute(
      "INSERT INTO bets(poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid) "
      "VALUES(?,?,'2026-09-30','Bettor',?,10000,'Winner','Winner',0,0)",
      (equal_id, params, bettor),
    )
    before = c.execute(
      "SELECT poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid,created_at,updated_at "
      "FROM bets ORDER BY row_id"
    ).fetchall()
    c.commit()

  _run(db, "upgrade", "head")

  with sqlite3.connect(db) as c:
    after = c.execute(
      "SELECT poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid,created_at,updated_at "
      "FROM bets ORDER BY row_id"
    ).fetchall()
    assert after == before
    assert c.execute(
      "SELECT winner_id,loser_id FROM bets WHERE row_id=?", (bet_id,)
    ).fetchone() == (winner, loser)
    assert c.execute(
      "SELECT winner_id,loser_id FROM bets WHERE poker_id=?", (equal_id,)
    ).fetchone() == (winner, winner)
    assert c.execute(
      "SELECT receipt_id,bet_id FROM bet_payment_receipt_bets"
    ).fetchall() == [(receipt_id, bet_id)]
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


def test_production_like_121_rows_backfill_without_id_coincidence(tmp_path):
  db = tmp_path / "production-shape.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, _, winner, loser, params = _seed_relations(c)
    for index in range(121):
      bettor = c.execute(
        "INSERT INTO users(telegram_id,name,is_admin,is_approved) VALUES(?,?,0,1) RETURNING row_id",
        (10_000 + index, f"Bettor {index}"),
      ).fetchone()[0]
      c.execute(
        "INSERT INTO bets(poker_id,params_id,date,better_name,better_id,size_kopecks,winner,looser,score,is_paid) "
        "VALUES(?,?,'2026-09-29',?,?,10000,'Winner','Loser',0,0)",
        (poker, params, f"Bettor {index}", bettor),
      )
    c.commit()

  _run(db, "upgrade", "head")

  with sqlite3.connect(db) as c:
    assert c.execute("SELECT COUNT(*) FROM bets").fetchone() == (121,)
    assert c.execute(
      "SELECT COUNT(*) FROM bets WHERE winner_id=? AND loser_id=?", (winner, loser)
    ).fetchone() == (121,)
    assert c.execute("SELECT MIN(row_id),MAX(row_id) FROM bets").fetchone() == (1, 121)
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []


@pytest.mark.parametrize(
  ("winner", "loser", "duplicate_winner", "message"),
  [
    (None, "Loser", False, "winner is NULL or empty"),
    ("", "Loser", False, "winner is NULL or empty"),
    ("0", "Loser", False, "matches 0 PokerData participants"),
    ("Missing", "Loser", False, "matches 0 PokerData participants"),
    ("Winner", "Loser", True, "matches 2 PokerData participants"),
  ],
)
def test_unresolvable_outcome_refuses_before_schema_change(
  tmp_path, winner, loser, duplicate_winner, message,
):
  db = tmp_path / "invalid.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, bettor, _, _, params = _seed_relations(c, duplicate_winner=duplicate_winner)
    _insert_legacy_bet(c, poker, bettor, params, winner=winner, loser=loser)
    c.commit()
  result = _run(db, "upgrade", "head", check=False)
  assert result.returncode != 0 and message in result.stderr
  with sqlite3.connect(db) as c:
    columns = {row[1] for row in c.execute("PRAGMA table_info('bets')")}
    assert "winner_id" not in columns and "loser_id" not in columns
    assert c.execute("SELECT version_num FROM alembic_version").fetchone() == (PREVIOUS,)


def test_missing_poker_and_orphan_participant_refuse_safely(tmp_path):
  for condition, expected in (("poker", "has no Poker"), ("user", "has no User")):
    db = tmp_path / f"{condition}.db"
    _run(db, "upgrade", PREVIOUS)
    with sqlite3.connect(db) as c:
      poker, bettor, winner, _, params = _seed_relations(c)
      _insert_legacy_bet(c, poker, bettor, params)
      c.execute("PRAGMA foreign_keys=OFF")
      if condition == "poker":
        c.execute("UPDATE bets SET poker_id=999999")
      else:
        c.execute("UPDATE poker_data SET player_id=999999 WHERE player_id=?", (winner,))
      c.commit()
    result = _run(db, "upgrade", "head", check=False)
    assert result.returncode != 0 and expected in result.stderr


def test_outcome_foreign_keys_restrict_invalid_ids_and_deletes(tmp_path):
  db = tmp_path / "constraints.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, bettor, winner, loser, params = _seed_relations(c)
    _insert_legacy_bet(c, poker, bettor, params)
    c.commit()
  _run(db, "upgrade", "head")
  with sqlite3.connect(db) as c:
    c.execute("PRAGMA foreign_keys=ON")
    for column in ("winner_id", "loser_id"):
      with pytest.raises(sqlite3.IntegrityError):
        c.execute(f"UPDATE bets SET {column}=999999")
    for user_id in (winner, loser):
      with pytest.raises(sqlite3.IntegrityError):
        c.execute("DELETE FROM users WHERE row_id=?", (user_id,))


def test_downgrade_preserves_legacy_bet_rows(tmp_path):
  db = tmp_path / "down.db"
  _run(db, "upgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    poker, bettor, _, _, params = _seed_relations(c)
    _insert_legacy_bet(c, poker, bettor, params)
    c.commit()
    before = c.execute("SELECT * FROM bets").fetchall()
  _run(db, "upgrade", "head")
  _run(db, "downgrade", PREVIOUS)
  with sqlite3.connect(db) as c:
    assert c.execute("SELECT * FROM bets").fetchall() == before
