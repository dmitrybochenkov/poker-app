from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from difflib import get_close_matches
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


def _closest_token(token: str, options: list[str], *, cutoff: float = 0.67) -> str | None:
  if token in options:
    return token
  found = get_close_matches(token, options, n=1, cutoff=cutoff)
  return found[0] if found else None


def _token_to_player(token: str) -> int | None:
  if token.isdigit():
    return int(token)
  words = {
    "один": 1,
    "два": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
  }
  near = _closest_token(token, list(words.keys()), cutoff=0.65)
  return words.get(near) if near else None


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

  # Grammar-aware recovery after trigger:
  # альфа <player|street> <action|...> [amount]
  tokens = s.split()
  if tokens:
    streets = ["префлоп", "флоп", "терн", "ривер"]
    actions = ["баттон", "пас", "фолд", "чек", "колл", "ставка", "рейз", "рейс", "победил", "победитель"]
    if tokens[0] == "улица" and len(tokens) > 1:
      tokens = tokens[1:]

    near_street = _closest_token(tokens[0], streets, cutoff=0.62)
    if near_street:
      return ParsedCommand(True, "street", None, None, near_street, raw, s, _now_utc_iso())

    idx = 0
    if tokens[0] == "игрок" and len(tokens) > 1:
      idx = 1
    p = _token_to_player(tokens[idx]) if idx < len(tokens) else None
    if p is not None and idx + 1 < len(tokens):
      near_action = _closest_token(tokens[idx + 1], actions, cutoff=0.62)
      amount = None
      for t in tokens[idx + 2 :]:
        if t.isdigit():
          amount = int(t)
          break
      if near_action == "баттон":
        return ParsedCommand(True, "new_hand", p, None, "preflop", raw, s, _now_utc_iso())
      if near_action in {"победил", "победитель"}:
        return ParsedCommand(True, "winner", p, None, None, raw, s, _now_utc_iso())
      if near_action in {"пас", "фолд"}:
        return ParsedCommand(True, "fold", p, amount, None, raw, s, _now_utc_iso())
      if near_action == "чек":
        return ParsedCommand(True, "check", p, amount, None, raw, s, _now_utc_iso())
      if near_action == "колл":
        return ParsedCommand(True, "call", p, amount, None, raw, s, _now_utc_iso())
      if near_action in {"ставка", "рейз", "рейс"} and isinstance(amount, int) and amount > 0:
        act = "bet" if near_action == "ставка" else "raise"
        return ParsedCommand(True, act, p, amount, None, raw, s, _now_utc_iso())

  return ParsedCommand(False, None, None, None, None, raw, s, _now_utc_iso(), "pattern_miss")
