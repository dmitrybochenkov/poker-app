from app.bot.shared.keyboards.reply_betting import ReplyBettingKbs
from app.bot.shared.keyboards.reply_navigation import ReplyNavigationKbs
from app.bot.shared.keyboards.reply_poker import ReplyPokerKbs


class ReplyKbs(ReplyNavigationKbs, ReplyBettingKbs, ReplyPokerKbs):
    """Compatibility facade for the established reply keyboard API."""
