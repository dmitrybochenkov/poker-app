from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


TRIGGER = "стол"


@dataclass
class ParsedCommand:
  ok: bool
  action: str | None
  player_num: int | None
  amount: int | None
  street: str | None
  raw_text: str
  normalized_text: str
  ts_utc: str
  error: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return {
      "ok_parse": self.ok,
      "action": self.action,
      "player_num": self.player_num,
      "amount": self.amount,
      "street": self.street,
      "raw_text": self.raw_text,
      "normalized_text": self.normalized_text,
      "ts_utc": self.ts_utc,
      "error": self.error,
    }


def _norm(text: str) -> str:
  return " ".join((text or "").lower().replace("ё", "е").split())


def _now_utc_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def parse_command(text: str) -> ParsedCommand:
  raw = text or ""
  s = _norm(raw)
  if not s:
    return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "empty")

  if TRIGGER not in s:
    return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "no_trigger")

  # Keep only the part after trigger, so table chat noise before trigger is ignored.
  s = s.split(TRIGGER, 1)[1].strip()

  if s == "новая раздача":
    return ParsedCommand(True, "new_hand", None, None, None, raw, s, _now_utc_iso())
  if s == "раздача завершена":
    return ParsedCommand(True, "hand_end", None, None, None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"улица (префлоп|флоп|терн|ривер)", s)
  if m:
    return ParsedCommand(True, "street", None, None, m.group(1), raw, s, _now_utc_iso())

  m = re.fullmatch(r"банк игрок (\d+) (\d+)", s)
  if m:
    return ParsedCommand(True, "win_bank", int(m.group(1)), int(m.group(2)), None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"игрок (\d+) (пас|фолд|чек)", s)
  if m:
    alias = m.group(2)
    action = "fold" if alias in {"пас", "фолд"} else "check"
    return ParsedCommand(True, action, int(m.group(1)), None, None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"игрок (\d+) (колл|ставка|рейз|олл-ин) (\d+)", s)
  if m:
    action_map = {
      "колл": "call",
      "ставка": "bet",
      "рейз": "raise",
      "олл-ин": "allin",
    }
    return ParsedCommand(
      True,
      action_map[m.group(2)],
      int(m.group(1)),
      int(m.group(3)),
      None,
      raw,
      s,
      _now_utc_iso(),
    )

  return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "pattern_miss")
