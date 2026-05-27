from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


DEFAULT_TRIGGERS = ("альфа",)


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
  s = (text or "").lower().replace("ё", "е")
  s = s.replace("—", " ").replace("–", " ").replace("-", " ")
  s = re.sub(r"[,:;.!?()\[\]{}\"'`«»]+", " ", s)
  s = " ".join(s.split())
  # Common ASR substitutions from noisy room speech.
  replacements = {
    "прехлоп": "префлоп",
    "прифлоп": "префлоп",
    "завернется": "завершена",
    "завершается": "завершена",
    "брок": "игрок",
    "грок": "игрок",
    "савка": "ставка",
    "савкача": "ставка",
    "пасс": "пас",
    "пассы": "пас",
    "пасы": "пас",
    "паз": "пас",
    "ререйз": "рейз",
    "батон": "баттон",
    "батан": "баттон",
    "паза": "пас",
    "флоб": "флоп",
    "кол.": "колл",
    "кол": "колл",
    "коль": "колл",
    "калл": "колл",
    "ков": "колл",
    "као": "колл",
    "км": "колл",
    "став": "ставка",
    "вставка": "ставка",
    "базы": "база",
    "сигнала": "сигнал",
    "сигналом": "сигнал",
    "алфа": "альфа",
  }
  for bad, good in replacements.items():
    s = re.sub(rf"\b{re.escape(bad)}\b", good, s)
  # Normalize frequent spoken numerals to digits.
  number_words = {
    "один": "1",
    "два": "2",
    "три": "3",
    "четыре": "4",
    "пять": "5",
    "шесть": "6",
    "семь": "7",
    "восемь": "8",
    "девять": "9",
    "десять": "10",
  }
  for word, digit in number_words.items():
    s = re.sub(rf"\b{word}\b", digit, s)
  return s


def _now_utc_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def parse_command(text: str, *, triggers: tuple[str, ...] = DEFAULT_TRIGGERS) -> ParsedCommand:
  raw = text or ""
  s = _norm(raw)
  if not s:
    return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "empty")

  # Accept a few frequent trigger distortions.
  trigger_aliases = set(triggers) | {
    "ваза",
    "базе",
    "базов",
    "базы",
    "поза",
    "сигнал",
    "сигнала",
    "сигналом",
    "сигналл",
    "альфа",
    "алфа",
  }
  first_word = s.split(" ", 1)[0] if s else ""
  if first_word not in trigger_aliases:
    return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "no_trigger")

  # Keep only the part after trigger word, so table chat noise before trigger is ignored.
  s = s.split(" ", 1)[1].strip() if " " in s else ""
  if not s:
    return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "empty_after_trigger")

  m = re.fullmatch(r"(\d+) баттон", s)
  if m:
    return ParsedCommand(True, "new_hand", int(m.group(1)), None, "preflop", raw, s, _now_utc_iso())
  m = re.fullmatch(r"баттон (\d+)", s)
  if m:
    return ParsedCommand(True, "new_hand", int(m.group(1)), None, "preflop", raw, s, _now_utc_iso())
  if s == "раздача завершена":
    return ParsedCommand(True, "hand_end", None, None, None, raw, s, _now_utc_iso())

  m = re.match(r"(?:улица )?(префлоп|флоп|терн|ривер)\b", s)
  if m:
    return ParsedCommand(True, "street", None, None, m.group(1), raw, s, _now_utc_iso())

  m = re.fullmatch(r"(\d+) победил", s)
  if m:
    return ParsedCommand(True, "winner", int(m.group(1)), None, None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"(?:игрок )?(\d+) (пас|фолд|чек)(?: (\d+))?", s)
  if m:
    alias = m.group(2)
    action = "fold" if alias in {"пас", "фолд"} else "check"
    amount = int(m.group(3)) if m.group(3) else None
    return ParsedCommand(True, action, int(m.group(1)), amount, None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"(?:игрок )?(\d+) колл(?: (\d+))?", s)
  if m:
    amount = int(m.group(2)) if m.group(2) else None
    return ParsedCommand(True, "call", int(m.group(1)), amount, None, raw, s, _now_utc_iso())

  # Manual correction command, e.g.:
  # "альфа правка 6 колл"
  # "альфа правка 3 рейз 200"
  m = re.fullmatch(r"правка (?:игрок )?(\d+) (пас|фолд|чек|колл|ставка|рейз|олл ин|оллин|рейс)(?: (\d+))?", s)
  if m:
    action_map = {
      "пас": "fix_fold",
      "фолд": "fix_fold",
      "чек": "fix_check",
      "колл": "fix_call",
      "ставка": "fix_bet",
      "рейз": "fix_raise",
      "рейс": "fix_raise",
      "олл ин": "fix_allin",
      "оллин": "fix_allin",
    }
    alias = m.group(2)
    amount = int(m.group(3)) if m.group(3) else None
    fix_action = action_map[alias]
    if fix_action in {"fix_bet", "fix_raise", "fix_allin"} and (amount is None or amount <= 0):
      return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "fix_amount_required")
    return ParsedCommand(True, fix_action, int(m.group(1)), amount, None, raw, s, _now_utc_iso())

  m = re.fullmatch(r"(?:игрок )?(\d+) (ставка|рейз|олл ин|оллин|рейс) (\d+)", s)
  if m:
    action_map = {
      "ставка": "bet",
      "рейз": "raise",
      "олл ин": "allin",
      "оллин": "allin",
      "рейс": "raise",
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
