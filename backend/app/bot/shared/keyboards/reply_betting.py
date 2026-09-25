from aiogram.types import ReplyKeyboardMarkup

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.reply_base import ReplyKeyboardBase, _button_labels


class ReplyBettingKbs(ReplyKeyboardBase):
    @classmethod
    def betting_tg(cls) -> ReplyKeyboardMarkup:
        return cls.betting_dynamic_tg(include_make_bet=True)

    @classmethod
    def betting_dynamic_tg(cls, *, include_make_bet: bool) -> ReplyKeyboardMarkup:
        buttons = []
        if include_make_bet:
            buttons.append(Buttons.betting.MAKE_BET)
        buttons.extend(
            [
                Buttons.betting.PAY_BET,
                Buttons.betting.CURRENT_TOURS,
                Buttons.betting.BETTING_STAT,
                Buttons.betting.TO_MAIN,
            ]
        )
        return cls.make_tg(
            _button_labels(buttons),
            adjust=1,
        )

    @classmethod
    def betting_vk(cls) -> str:
        return cls.betting_dynamic_vk(include_make_bet=True)

    @classmethod
    def betting_dynamic_vk(cls, *, include_make_bet: bool) -> str:
        buttons = []
        if include_make_bet:
            buttons.append(Buttons.betting.MAKE_BET)
        buttons.extend(
            [
                Buttons.betting.PAY_BET,
                Buttons.betting.CURRENT_TOURS,
                Buttons.betting.BETTING_STAT,
                Buttons.betting.TO_MAIN,
            ]
        )
        return cls.make_vk(
            _button_labels(buttons),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def betting_current_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.betting_current.REG_TOURNAMENT,
                    Buttons.betting_current.YEAR_TOURNAMENT,
                    Buttons.betting_current.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def betting_current_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.betting_current.REG_TOURNAMENT,
                    Buttons.betting_current.YEAR_TOURNAMENT,
                    Buttons.betting_current.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def betting_info_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.bettingInfo.BETTING_RULES,
                    Buttons.bettingInfo.BETTING_ACH_INFO,
                    Buttons.bettingInfo.BETTING_STAT_INFO,
                    Buttons.bettingInfo.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def betting_info_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.bettingInfo.BETTING_RULES,
                    Buttons.bettingInfo.BETTING_ACH_INFO,
                    Buttons.bettingInfo.BETTING_STAT_INFO,
                    Buttons.bettingInfo.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )
