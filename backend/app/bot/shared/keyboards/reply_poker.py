from aiogram.types import ReplyKeyboardMarkup

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.reply_base import ReplyKeyboardBase, _button_labels


class ReplyPokerKbs(ReplyKeyboardBase):
    @classmethod
    def poker_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.main.NEXT_POKER_DATE,
                    Buttons.poker.POKER_STAT,
                    Buttons.poker.HISTORY,
                    Buttons.poker.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def poker_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.main.NEXT_POKER_DATE,
                    Buttons.poker.POKER_STAT,
                    Buttons.poker.HISTORY,
                    Buttons.poker.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def poker_info_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.pokerInfo.POKER_ACH_INFO,
                    Buttons.pokerInfo.POKER_STAT_INFO,
                    Buttons.pokerInfo.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def poker_info_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.pokerInfo.POKER_ACH_INFO,
                    Buttons.pokerInfo.POKER_STAT_INFO,
                    Buttons.pokerInfo.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def room_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.room.STATUS,
                    Buttons.room.BUYIN,
                    Buttons.room.POKER_ADMIN,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def room_admin_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.room.STATUS,
                    Buttons.room.BUYIN,
                    Buttons.room.POKER_ADMIN,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def room_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.room.STATUS,
                    Buttons.room.BUYIN,
                    Buttons.room.POKER_ADMIN,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def room_admin_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.room.STATUS,
                    Buttons.room.BUYIN,
                    Buttons.room.POKER_ADMIN,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def admin_room_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.admin_room.CORRECT_POKER,
                    Buttons.admin_room.FINISH_POKER,
                    Buttons.admin_room.TO_ROOM,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def admin_room_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.admin_room.CORRECT_POKER,
                    Buttons.admin_room.FINISH_POKER,
                    Buttons.admin_room.TO_ROOM,
                    Buttons.room.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def admin_room_correct_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.admin_room_correct.SET_CASHIER,
                    Buttons.admin_room_correct.ADD_PLAYER,
                    Buttons.admin_room_correct.REMOVE_PLAYER,
                    Buttons.admin_room_correct.BUYIN_CORRECT,
                    Buttons.admin_room_correct.TO_ADMIN_ROOM,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def admin_room_correct_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.admin_room_correct.SET_CASHIER,
                    Buttons.admin_room_correct.ADD_PLAYER,
                    Buttons.admin_room_correct.REMOVE_PLAYER,
                    Buttons.admin_room_correct.BUYIN_CORRECT,
                    Buttons.admin_room_correct.TO_ADMIN_ROOM,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )
