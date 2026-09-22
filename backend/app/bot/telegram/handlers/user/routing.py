from aiogram import F
from aiogram.filters import CommandStart

from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.texts.inline.telegram.user import routing as InlineText
from app.bot.telegram.states import PollState, RegistrationState

from . import bets, betting_stats, navigation, poker, poker_stats, polls, registration
from .common import router

router.message(CommandStart())(registration.start_command)
router.message(F.text == Buttons.new_user.REGISTRATION.value)(registration.start_registration)
router.message(F.text == Buttons.new_user.ABOUT.value)(registration.show_bot_info)
router.message(F.text == Buttons.room.STATUS.value)(registration.show_user_status)
router.message(F.text == Buttons.main.ROOM.value)(poker.join_poker_room)
router.message(F.text == Buttons.room.POKER_ADMIN.value)(poker.open_room_admin_panel)
router.message((F.text == Buttons.poker.POLL.value) | (F.text == Buttons.poll_menu.VOTE.value))(
    polls.start_room_poll
)
router.message(F.text == Buttons.poll_menu.RESULTS.value)(polls.show_poll_results)
router.callback_query(F.data == "poll_noop")(polls.poll_noop)
router.callback_query(F.data.startswith("poll_page:"))(polls.poll_page_nav)
router.callback_query(F.data.startswith("poll_day:"))(polls.poll_day_toggle)
router.callback_query(F.data.startswith("poll_suggest:"))(polls.poll_suggest_day)
router.message(PollState.waiting_for_custom_day)(polls.poll_suggest_day_input)
router.callback_query(F.data == "poll_done")(polls.poll_done)
router.callback_query(F.data == "poll_cancel")(polls.poll_cancel)
router.message(F.text == Buttons.main.BETTING.value)(navigation.open_betting_menu)
router.message(F.text == Buttons.main.POKER.value)(navigation.open_poker_menu)
router.message(F.text == Buttons.main.INFO.value)(navigation.open_info_menu)
router.message(F.text == Buttons.main.NEXT_POKER_DATE.value)(navigation.open_next_poker_date_menu)
router.message(F.text == Buttons.main.ADMIN.value)(navigation.open_admin_panel)
router.message(F.text == Buttons.admin_main.TO_MAIN.value)(navigation.back_from_admin_to_main)
router.message(F.text == Buttons.betting.TO_MAIN.value)(navigation.back_to_main_from_betting)
router.message(F.text == Buttons.poker.TO_MAIN.value)(navigation.back_to_main_from_poker)
router.message(F.text == Buttons.room.TO_MAIN.value)(navigation.back_to_main_from_room)
router.message(F.text == Buttons.poll_menu.TO_MAIN.value)(navigation.back_to_main_from_poll_menu)
router.message(F.text.in_({Buttons.main_info.POKER_INFO.value, InlineText.MODULE_TEXT_01}))(
    navigation.show_poker_info
)
router.message(F.text.in_({Buttons.main_info.BETTING_INFO.value, InlineText.MODULE_TEXT_02}))(
    navigation.show_betting_info
)
router.message(F.text == Buttons.main_info.TO_MAIN.value)(navigation.back_to_main_from_info)
router.message(F.text == Buttons.bettingInfo.BETTING_RULES.value)(navigation.show_betting_rules)
router.message(F.text == Buttons.bettingInfo.BETTING_STAT_INFO.value)(
    navigation.show_betting_stat_info
)
router.message(F.text == Buttons.bettingInfo.BETTING_ACH_INFO.value)(
    navigation.show_betting_achievement_info
)
router.message(F.text == Buttons.pokerInfo.POKER_STAT_INFO.value)(navigation.show_poker_stat_info)
router.message(F.text == Buttons.pokerInfo.POKER_ACH_INFO.value)(
    navigation.show_poker_achievement_info
)
router.message(
    (F.text == Buttons.poker.HISTORY.value) | (F.text == Buttons.pokerInfo.HISTORY.value)
)(poker_stats.show_poker_history_years)
router.callback_query(F.data == "pokerhist_cancel")(poker_stats.poker_history_cancel)
router.callback_query(F.data.startswith("pokerhistyear:"))(poker_stats.poker_history_year_pick)
router.callback_query(F.data.startswith("pokerhistpage:"))(poker_stats.poker_history_page)
router.callback_query(F.data.startswith("pokerhistdate:"))(poker_stats.poker_history_date_pick)
router.message(F.text == Buttons.poker.POKER_STAT.value)(poker_stats.show_poker_stat_indicators)
router.callback_query(F.data.startswith("pokerstatyear_page:"))(poker_stats.poker_stat_year_page)
router.callback_query(F.data.startswith("pokerstatyear_toggle:"))(
    poker_stats.poker_stat_year_toggle
)
router.callback_query(F.data == "pokerstatyear_cancel")(poker_stats.poker_stat_year_cancel)
router.callback_query(F.data == "pokerstatyear_done")(poker_stats.poker_stat_year_done)
router.callback_query(F.data.startswith("pokerstat_page:"))(poker_stats.poker_stat_page)
router.callback_query(F.data.startswith("pokerstat_toggle:"))(
    poker_stats.poker_stat_indicator_selected
)
router.callback_query(F.data == "pokerstat_done")(poker_stats.poker_stat_done)
router.callback_query(F.data == "pokerstat_cancel")(poker_stats.poker_stat_cancel)
router.callback_query(F.data.startswith("pokerstatsort_page:"))(poker_stats.poker_stat_sort_page)
router.callback_query(F.data.startswith("pokerstatsort_toggle:"))(
    poker_stats.poker_stat_sort_toggle
)
router.callback_query(F.data == "pokerstatsort_cancel")(poker_stats.poker_stat_sort_cancel)
router.callback_query(F.data == "pokerstatsort_done")(poker_stats.poker_stat_sort_done)
router.message(F.text == Buttons.betting.CURRENT_TOURS.value)(
    betting_stats.show_current_betting_tournaments
)
router.message(F.text == Buttons.betting_current.REG_TOURNAMENT.value)(
    betting_stats.show_regular_betting_tournament_stat
)
router.message(F.text == Buttons.betting_current.YEAR_TOURNAMENT.value)(
    betting_stats.show_year_betting_tournament_stat
)
router.message(F.text == Buttons.betting_current.TO_MAIN.value)(
    betting_stats.back_to_betting_from_current_tournaments
)
router.message(F.text == Buttons.betting.BETTING_STAT.value)(
    betting_stats.show_betting_stat_indicators
)
router.callback_query(F.data.startswith("betstatyear_page:"))(betting_stats.betting_stat_year_page)
router.callback_query(F.data.startswith("betstatyear_toggle:"))(
    betting_stats.betting_stat_year_toggle
)
router.callback_query(F.data == "betstatyear_cancel")(betting_stats.betting_stat_year_cancel)
router.callback_query(F.data == "betstatyear_done")(betting_stats.betting_stat_year_done)
router.callback_query(F.data.startswith("betstatmode:"))(betting_stats.betting_stat_mode_selected)
router.callback_query(F.data.startswith("betstat_page:"))(betting_stats.betting_stat_page)
router.callback_query(F.data.startswith("betstat_toggle:"))(
    betting_stats.betting_stat_indicator_selected
)
router.callback_query(F.data == "betstat_done")(betting_stats.betting_stat_done)
router.callback_query(F.data == "betstat_cancel")(betting_stats.betting_stat_cancel)
router.callback_query(F.data.startswith("betstatsort_page:"))(betting_stats.betting_stat_sort_page)
router.callback_query(F.data.startswith("betstatsort_toggle:"))(
    betting_stats.betting_stat_sort_toggle
)
router.callback_query(F.data == "betstatsort_cancel")(betting_stats.betting_stat_sort_cancel)
router.callback_query(F.data == "betstatsort_done")(betting_stats.betting_stat_sort_done)
router.message(F.text == Buttons.betting.PAY_BET.value)(bets.start_pay_bet)
router.message(F.text == Buttons.betting.MAKE_BET.value)(bets.start_make_bet)
router.callback_query(F.data.startswith("registration_played_before:"))(
    registration.choose_registration_branch
)
router.message(RegistrationState.waiting_for_played_before_answer)(
    registration.repeat_registration_branch_prompt
)
router.callback_query(F.data.startswith("registration_existing:"))(
    registration.finish_existing_row_id_registration
)
router.callback_query(F.data.startswith("registration_existing_page:"))(
    registration.registration_existing_page
)
router.callback_query(F.data.startswith("registration_platform:"))(
    registration.choose_registration_platform
)
router.message(RegistrationState.waiting_for_new_name)(registration.finish_registration)
router.callback_query(F.data.startswith("registration_optional:"))(
    registration.choose_optional_registration_data
)
router.callback_query(F.data.startswith("bet_tournament:"))(bets.choose_bet_tournament)
router.callback_query(F.data.startswith("bet_size:"))(bets.choose_bet_size)
router.callback_query(F.data.startswith("bet_winner:"))(bets.choose_bet_winner)
router.callback_query(F.data.startswith("bet_loser:"))(bets.choose_bet_loser)
router.callback_query(F.data.startswith("bet_confirm:"))(bets.confirm_bet)
router.message(RegistrationState.waiting_for_bet_amount)(bets.repeat_bet_inline_flow)
router.message(RegistrationState.waiting_for_bet_payment_receipt)(bets.process_bet_payment_receipt)
router.message(F.text.regexp(r"^\d{1,9}$"))(poker.process_chips_input)
router.message(RegistrationState.waiting_for_bank_name)(registration.save_optional_bank_name)
router.message(RegistrationState.waiting_for_phone)(registration.save_optional_phone)
router.message(RegistrationState.waiting_for_optional_details_action)(
    registration.repeat_optional_registration_prompt
)
