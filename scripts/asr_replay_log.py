from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


def _fmt_rub(v: int) -> str:
  return f"{v} ₽"


def _next_seat(cur: int, players: int) -> int:
  return 1 if cur >= players else cur + 1


def _parse_ts(ts: str | None) -> datetime | None:
  if not ts:
    return None
  try:
    return datetime.fromisoformat(ts)
  except Exception:
    return None


@dataclass
class HandState:
  hand_no: int
  button: int
  street: str = "preflop"
  current_bet: int = 0
  pot: int = 0
  active_players: set[int] = field(default_factory=set)
  folded_players: set[int] = field(default_factory=set)
  put_total: dict[int, int] = field(default_factory=lambda: defaultdict(int))
  put_street: dict[int, int] = field(default_factory=lambda: defaultdict(int))
  winner: int | None = None


def _start_hand(*, hand_no: int, button: int, players: int, sb: int, bb: int) -> HandState:
  state = HandState(hand_no=hand_no, button=button)
  state.active_players = set(range(1, players + 1))
  sb_player = _next_seat(button, players)
  bb_player = _next_seat(sb_player, players)
  state.put_total[sb_player] += sb
  state.put_street[sb_player] += sb
  state.put_total[bb_player] += bb
  state.put_street[bb_player] += bb
  state.pot += sb + bb
  state.current_bet = bb
  return state


def _apply_event(state: HandState, evt: dict, *, warnings: list[str]) -> None:
  action = evt.get("action")
  p = evt.get("player_num")
  amount = evt.get("amount")

  if action == "street":
    state.street = str(evt.get("street") or state.street)
    state.current_bet = 0
    state.put_street = defaultdict(int)
    return

  if not isinstance(p, int):
    return
  if p not in state.active_players:
    warnings.append(f"hand#{state.hand_no}: player {p} action after fold/invalid")
    return

  if action == "fold":
    if p in state.folded_players:
      warnings.append(f"hand#{state.hand_no}: duplicate fold by player {p}")
      return
    state.folded_players.add(p)
    state.active_players.discard(p)
    return

  if action == "check":
    need = max(0, state.current_bet - int(state.put_street.get(p, 0)))
    if need != 0:
      warnings.append(f"hand#{state.hand_no}: invalid check by player {p}, need {need}")
    if isinstance(amount, int) and amount > 0:
      warnings.append(f"hand#{state.hand_no}: check by player {p} ignored amount={amount}")
    return

  if action == "call":
    put_before = int(state.put_street.get(p, 0))
    need = max(0, state.current_bet - put_before)
    add = need
    if isinstance(amount, int) and amount > 0:
      # Spoken amount for call is interpreted as total player contribution on this street.
      add = max(0, int(amount) - put_before)
      if add != need:
        warnings.append(
          f"hand#{state.hand_no}: call amount mismatch for player {p}: spoken_total={amount}, expected_total={state.current_bet}, add={add}, expected_add={need}"
        )
    state.put_street[p] += add
    state.put_total[p] += add
    state.pot += add
    return

  if action in {"bet", "raise", "allin"}:
    if not isinstance(amount, int) or amount <= 0:
      warnings.append(f"hand#{state.hand_no}: invalid amount for {action} by player {p}")
      return
    state.put_street[p] += int(amount)
    state.put_total[p] += int(amount)
    state.pot += int(amount)
    if state.put_street[p] > state.current_bet:
      state.current_bet = state.put_street[p]
    return

  if action == "winner":
    state.winner = p


def _evaluate_hand(
  *,
  hand_no: int,
  button: int,
  players: int,
  sb: int,
  bb: int,
  events: list[dict],
  warnings: list[str],
) -> HandState:
  state = _start_hand(hand_no=hand_no, button=button, players=players, sb=sb, bb=bb)
  for evt in events:
    _apply_event(state, evt, warnings=warnings)
  return state


def _map_fix_action(action: str | None) -> str | None:
  fix_map = {
    "fix_fold": "fold",
    "fix_check": "check",
    "fix_call": "call",
    "fix_bet": "bet",
    "fix_raise": "raise",
    "fix_allin": "allin",
  }
  return fix_map.get(str(action))


def main() -> None:
  parser = argparse.ArgumentParser(description="Replay ASR poker log and print derived hand summaries")
  parser.add_argument("--in", dest="inp", default="asr_events.jsonl", help="Input JSONL path")
  parser.add_argument("--players", type=int, default=7, help="Seats count")
  parser.add_argument("--sb", type=int, default=10, help="Small blind amount")
  parser.add_argument("--bb", type=int, default=20, help="Big blind amount")
  parser.add_argument(
    "--dedupe-window-sec",
    type=float,
    default=2.5,
    help="Treat same player+action(+amount/+street) inside this window as duplicate",
  )
  args = parser.parse_args()

  src = Path(args.inp)
  if not src.exists():
    raise SystemExit(f"Log file not found: {src}")

  parsed_total = 0
  hands_started = 0
  warnings: list[str] = []
  totals_put: dict[int, int] = defaultdict(int)
  totals_won: dict[int, int] = defaultdict(int)
  current_hand_no: int | None = None
  current_button: int | None = None
  current_events: list[dict] = []
  current_street_ctx: str = "preflop"
  # key -> last timestamp; used only for post-processing dedupe (raw log stays untouched)
  last_action_ts: dict[tuple[int, str, int | None, str | None, int], datetime] = {}
  suppressed_duplicates: list[str] = []
  applied_fixes: list[str] = []
  amount_consensus_changes: list[str] = []
  # (hand_no, street, player, action) -> amount -> cnt
  amount_votes: dict[tuple[int, str, int, str], dict[int, int]] = defaultdict(lambda: defaultdict(int))

  def close_hand() -> None:
    nonlocal current_hand_no, current_button, current_events, current_street_ctx
    if current_hand_no is None or current_button is None:
      return
    hand_warnings: list[str] = []
    final_state = _evaluate_hand(
      hand_no=int(current_hand_no),
      button=int(current_button),
      players=int(args.players),
      sb=int(args.sb),
      bb=int(args.bb),
      events=current_events,
      warnings=hand_warnings,
    )
    warnings.extend(hand_warnings)
    for p, val in final_state.put_total.items():
      totals_put[p] += int(val)
    if final_state.winner is not None:
      totals_won[int(final_state.winner)] += int(final_state.pot)
    current_hand_no = None
    current_button = None
    current_events = []
    current_street_ctx = "preflop"

  with src.open("r", encoding="utf-8") as f:
    for line in f:
      line = line.strip()
      if not line:
        continue
      evt = json.loads(line)
      if not evt.get("ok_parse"):
        continue
      parsed_total += 1
      action = evt.get("action")
      if action == "new_hand":
        close_hand()
        last_action_ts.clear()
        amount_votes.clear()
        button = evt.get("player_num")
        if not isinstance(button, int):
          warnings.append("new_hand without button")
          continue
        hands_started += 1
        current_hand_no = hands_started
        current_button = button
        current_events = []
        current_street_ctx = "preflop"
        continue
      if current_hand_no is None:
        continue

      # Drop near-identical duplicates in math, but keep an audit line.
      ts = _parse_ts(evt.get("ts_utc"))
      p = evt.get("player_num")
      amount = evt.get("amount")
      street = evt.get("street")
      if isinstance(p, int):
        dedupe_key = (int(p), str(action), int(amount) if isinstance(amount, int) else None, str(street) if isinstance(street, str) else None, int(current_hand_no))
        prev_ts = last_action_ts.get(dedupe_key)
        if prev_ts is not None and ts is not None:
          delta = (ts - prev_ts).total_seconds()
          if 0 <= delta <= float(args.dedupe_window_sec):
            suppressed_duplicates.append(
              f"hand#{current_hand_no}: duplicate suppressed p={p} action={action} amount={amount} street={street} dt={delta:.2f}s text={evt.get('raw_text')}"
            )
            continue
        if ts is not None:
          last_action_ts[dedupe_key] = ts

      # Manual correction: replace last player action on current street.
      mapped_fix = _map_fix_action(action)
      if mapped_fix is not None and isinstance(p, int):
        replaced_idx = None
        for i in range(len(current_events) - 1, -1, -1):
          prev = current_events[i]
          if prev.get("_street_ctx") != current_street_ctx:
            continue
          if prev.get("player_num") != p:
            continue
          if prev.get("action") not in {"fold", "check", "call", "bet", "raise", "allin"}:
            continue
          replaced_idx = i
          break
        replacement = {
          "action": mapped_fix,
          "player_num": p,
          "amount": int(amount) if isinstance(amount, int) else None,
          "street": None,
          "raw_text": evt.get("raw_text"),
          "_street_ctx": current_street_ctx,
        }
        if replaced_idx is None:
          current_events.append(replacement)
          applied_fixes.append(
            f"hand#{current_hand_no} street={current_street_ctx}: fix appended p={p} -> {mapped_fix} amount={replacement.get('amount')}"
          )
        else:
          prev = current_events[replaced_idx]
          current_events[replaced_idx] = replacement
          applied_fixes.append(
            f"hand#{current_hand_no} street={current_street_ctx}: fix replaced p={p} {prev.get('action')}({prev.get('amount')}) -> {mapped_fix}({replacement.get('amount')})"
          )
        continue

      # Amount consensus for noisy bet sizing on same street.
      if action in {"bet", "raise", "allin"} and isinstance(p, int) and isinstance(amount, int):
        vote_key = (int(current_hand_no), str(current_street_ctx), int(p), str(action))
        amount_votes[vote_key][int(amount)] += 1
        voted_amounts = amount_votes[vote_key]
        best_amount, best_cnt = max(voted_amounts.items(), key=lambda it: (it[1], it[0]))
        if int(amount) != int(best_amount) and best_cnt >= 2:
          amount_consensus_changes.append(
            f"hand#{current_hand_no} street={current_street_ctx}: p={p} {action} {amount} -> {best_amount} (mode={best_cnt})"
          )
          evt = dict(evt)
          evt["amount"] = int(best_amount)

      evt_copy = {
        "action": action,
        "player_num": p,
        "amount": evt.get("amount"),
        "street": street,
        "raw_text": evt.get("raw_text"),
        "_street_ctx": current_street_ctx,
      }
      current_events.append(evt_copy)
      if action == "street" and isinstance(street, str):
        current_street_ctx = str(street)
      if action == "hand_end":
        close_hand()

  close_hand()

  players = sorted(set(totals_put) | set(totals_won))
  print(f"Hands started: {hands_started}")
  print(f"Parsed events: {parsed_total}")
  print("")
  print("Per-player summary")
  print("------------------")
  for p in players:
    put = int(totals_put.get(p, 0))
    won = int(totals_won.get(p, 0))
    net = won - put
    sign = "+" if net >= 0 else ""
    print(f"Игрок {p}: put {_fmt_rub(put)} | won {_fmt_rub(won)} | net {sign}{_fmt_rub(net)}")

  if warnings:
    print("")
    print("Warnings")
    print("--------")
    for w in warnings[:40]:
      print(w)
    if len(warnings) > 40:
      print(f"... and {len(warnings) - 40} more")

  if suppressed_duplicates:
    print("")
    print("Suppressed duplicates")
    print("---------------------")
    for row in suppressed_duplicates[:60]:
      print(row)
    if len(suppressed_duplicates) > 60:
      print(f"... and {len(suppressed_duplicates) - 60} more")

  if applied_fixes:
    print("")
    print("Applied fixes")
    print("------------")
    for row in applied_fixes[:80]:
      print(row)
    if len(applied_fixes) > 80:
      print(f"... and {len(applied_fixes) - 80} more")

  if amount_consensus_changes:
    print("")
    print("Amount consensus changes")
    print("------------------------")
    for row in amount_consensus_changes[:80]:
      print(row)
    if len(amount_consensus_changes) > 80:
      print(f"... and {len(amount_consensus_changes) - 80} more")


if __name__ == "__main__":
  main()
