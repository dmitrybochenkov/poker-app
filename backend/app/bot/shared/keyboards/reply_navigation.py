from aiogram.types import ReplyKeyboardMarkup

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.keyboards.reply_base import ReplyKeyboardBase, _button_labels


class ReplyNavigationKbs(ReplyKeyboardBase):
    @classmethod
    def new_user_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.new_user.ABOUT,
                    Buttons.new_user.REGISTRATION,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def new_user_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.new_user.ABOUT,
                    Buttons.new_user.REGISTRATION,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def main_tg(cls) -> ReplyKeyboardMarkup:
        return cls.main_dynamic_tg(is_admin=False, has_active_poker=False, has_active_poll=False)

    @classmethod
    def admin_main_entry_tg(cls) -> ReplyKeyboardMarkup:
        return cls.main_dynamic_tg(is_admin=True, has_active_poker=False, has_active_poll=False)

    @classmethod
    def main_vk(cls) -> str:
        return cls.main_dynamic_vk(is_admin=False, has_active_poker=False, has_active_poll=False)

    @classmethod
    def admin_main_entry_vk(cls) -> str:
        return cls.main_dynamic_vk(is_admin=True, has_active_poker=False, has_active_poll=False)

    @classmethod
    def main_dynamic_tg(
        cls,
        *,
        is_admin: bool,
        has_active_poker: bool,
        has_active_poll: bool,
    ) -> ReplyKeyboardMarkup:
        buttons = [Buttons.main.ROOM, Buttons.main.POKER, Buttons.main.BETTING, Buttons.main.INFO]
        buttons.append(Buttons.main.ADMIN)
        return cls.make_tg(_button_labels(buttons), adjust=1)

    @classmethod
    def main_dynamic_vk(
        cls,
        *,
        is_admin: bool,
        has_active_poker: bool,
        has_active_poll: bool,
    ) -> str:
        buttons = [Buttons.main.ROOM, Buttons.main.POKER, Buttons.main.BETTING, Buttons.main.INFO]
        buttons.append(Buttons.main.ADMIN)
        return cls.make_vk(_button_labels(buttons), adjust=1, one_time=False, color="primary")

    @classmethod
    def poll_menu_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.poll_menu.VOTE,
                    Buttons.poll_menu.RESULTS,
                    Buttons.poll_menu.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def poll_menu_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.poll_menu.VOTE,
                    Buttons.poll_menu.RESULTS,
                    Buttons.poll_menu.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def main_info_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.main_info.POKER_INFO,
                    Buttons.main_info.BETTING_INFO,
                    Buttons.main_info.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def main_info_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.main_info.POKER_INFO,
                    Buttons.main_info.BETTING_INFO,
                    Buttons.main_info.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )

    @classmethod
    def admin_main_tg(cls) -> ReplyKeyboardMarkup:
        return cls.make_tg(
            _button_labels(
                [
                    Buttons.admin_main.CREATE_POLL,
                    Buttons.admin_main.START_POKER,
                    Buttons.admin_main.MAKE_ADMIN,
                    Buttons.admin_main.TO_MAIN,
                ]
            ),
            adjust=1,
        )

    @classmethod
    def admin_main_vk(cls) -> str:
        return cls.make_vk(
            _button_labels(
                [
                    Buttons.admin_main.CREATE_POLL,
                    Buttons.admin_main.START_POKER,
                    Buttons.admin_main.MAKE_ADMIN,
                    Buttons.admin_main.TO_MAIN,
                ]
            ),
            adjust=1,
            one_time=False,
            color="primary",
        )
