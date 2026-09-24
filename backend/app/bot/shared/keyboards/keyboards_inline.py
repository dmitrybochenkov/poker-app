"""Compatibility facade for the established shared inline keyboard API."""

from .inline_betting import BettingInlineKbs
from .inline_poker import PokerInlineKbs
from .inline_polls import PollInlineKbs
from .inline_registration import RegistrationInlineKbs
from .inline_statistics import StatisticsInlineKbs


class InlineKbs(
  RegistrationInlineKbs,
  PokerInlineKbs,
  BettingInlineKbs,
  StatisticsInlineKbs,
  PollInlineKbs,
):
  pass
