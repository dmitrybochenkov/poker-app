from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path


def _fmt_rub(v: int) -> str:
  return f"{v} ₽"


def main() -> None:
  parser = argparse.ArgumentParser(description="Replay ASR poker log and print simple per-player totals")
  parser.add_argument("--in", dest="inp", default="asr_events.jsonl", help="Input JSONL path")
  args = parser.parse_args()

  src = Path(args.inp)
  if not src.exists():
    raise SystemExit(f"Log file not found: {src}")

  put_by_player: dict[int, int] = defaultdict(int)
  won_by_player: dict[int, int] = defaultdict(int)
  hands_total = 0
  parsed_total = 0

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
      player = evt.get("player_num")
      amount = evt.get("amount")

      if action == "new_hand":
        hands_total += 1
      elif action in {"bet", "call", "raise", "allin"} and isinstance(player, int) and isinstance(amount, int):
        put_by_player[player] += amount
      elif action == "win_bank" and isinstance(player, int) and isinstance(amount, int):
        won_by_player[player] += amount

  players = sorted(set(put_by_player) | set(won_by_player))
  print(f"Hands started: {hands_total}")
  print(f"Parsed events: {parsed_total}")
  print("")
  print("Per-player summary")
  print("------------------")
  for p in players:
    put = put_by_player.get(p, 0)
    won = won_by_player.get(p, 0)
    net = won - put
    sign = "+" if net >= 0 else ""
    print(f"Игрок {p}: put {_fmt_rub(put)} | won {_fmt_rub(won)} | net {sign}{_fmt_rub(net)}")


if __name__ == "__main__":
  main()
