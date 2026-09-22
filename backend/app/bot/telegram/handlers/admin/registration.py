from aiogram import F
from app.bot.shared.buttons.buttons import Buttons
from app.bot.telegram.states import AdminPokerState, RegistrationState

from . import bets, buyins, management, players, poker, polls, registrations
from .common import router

router.message(F.text == Buttons.admin_main.START_POKER.value)(poker.start_poker_menu)
router.callback_query(F.data.startswith("pokerstart:"))(poker.start_poker_with_param)
router.message(F.text == Buttons.admin_room.FINISH_POKER.value)(poker.finish_poker)
router.message(F.text == Buttons.admin_room.CALCULATE_POKER.value)(poker.calculate_poker)
router.callback_query(F.data == "pokercalc:run")(poker.calculate_poker_inline)
router.message(F.text == Buttons.admin_room.START_BETTING.value)(bets.start_betting)
router.callback_query(F.data == "pokerstartbetting:inline")(bets.start_betting_inline)
router.message(F.text == Buttons.admin_main.CREATE_POLL.value)(polls.create_poll_menu)
router.callback_query(F.data == "polladmin_other")(polls.create_poll_choose_other)
router.callback_query(F.data == "polladmin_cancel")(polls.create_poll_cancel)
router.callback_query(F.data.startswith("polladmin_month:"))(polls.create_poll_set_month)
router.message(
    (F.text == Buttons.admin_room.SET_CASHIER.value)
    | (F.text == Buttons.admin_room_correct.SET_CASHIER.value)
)(poker.set_cashier_menu)
router.message(F.text == Buttons.admin_room.CORRECT_POKER.value)(poker.open_correct_poker_menu)
router.message(F.text == Buttons.admin_room_correct.TO_ADMIN_ROOM.value)(
    poker.back_from_correct_poker_menu
)
router.callback_query(F.data.startswith("pokercashier:"))(poker.set_cashier_callback)
router.callback_query(F.data.startswith("pokerroomcashier:"))(poker.set_cashier_from_room_callback)
router.callback_query(F.data.startswith("pokerroommanage:"))(players.poker_room_manage_callback)
router.callback_query(F.data.startswith("pokerroomapprove:"))(players.poker_room_approve_callback)
router.callback_query(F.data.startswith("pokerroomreject:"))(players.poker_room_reject_callback)
router.message(
    (F.text == Buttons.admin_room.ADD_PLAYER.value)
    | (F.text == Buttons.admin_room_correct.ADD_PLAYER.value)
)(players.add_player_menu)
router.callback_query(F.data.startswith("pokeradd:"))(players.add_player_callback)
router.callback_query(F.data.startswith("pokeraddnew:"))(players.add_player_new_callback)
router.callback_query(F.data.startswith("pokeraddcancel:"))(players.add_player_cancel_callback)
router.message(AdminPokerState.waiting_for_new_player_name)(players.add_new_player_name_input)
router.message(
    (F.text == Buttons.admin_room.REMOVE_PLAYER.value)
    | (F.text == Buttons.admin_room_correct.REMOVE_PLAYER.value)
)(players.remove_player_menu)
router.callback_query(F.data.startswith("pokerremove:"))(players.remove_player_callback)
router.message(F.text == Buttons.admin_room.UNBAN_PLAYER.value)(players.unban_player_menu)
router.callback_query(F.data.startswith("pokerunban:"))(players.unban_player_callback)
router.message(
    (F.text == Buttons.room.BUYIN.value)
    | (F.text == Buttons.admin_room_correct.BUYIN_CORRECT.value)
)(buyins.buyin_menu)
router.callback_query(F.data.startswith("pokerbuyin:"))(buyins.buyin_select_callback)
router.callback_query(F.data.startswith("pokerbuyincorrect:"))(buyins.buyin_correct_select_callback)
router.message(AdminPokerState.waiting_for_buyin_correct_amount)(buyins.buyin_correct_amount_input)
router.callback_query(F.data.startswith("pokerbuyincorrectconfirm:"))(
    buyins.buyin_correct_confirm_callback
)
router.callback_query(F.data.startswith("pokerbuyincount:"))(buyins.buyin_count_callback)
router.callback_query(F.data.startswith("pokerbuyincancel:"))(buyins.buyin_cancel_callback)
router.callback_query(F.data.startswith("pokercashout:"))(buyins.cashout_select_callback)
router.message(AdminPokerState.waiting_for_cashout_amount)(buyins.cashout_amount_input)
router.message(F.text == Buttons.admin_main.MAKE_ADMIN.value)(management.make_admin_menu)
router.callback_query(F.data.startswith("makeadmin:"))(management.make_admin_select_callback)
router.message(F.text == Buttons.admin_room.TO_ROOM.value)(management.back_to_room_admin_panel)
router.callback_query(F.data.startswith("approve:"))(registrations.approve_registration_callback)
router.callback_query(F.data.startswith("betreceipt:"))(bets.bet_receipt_manual_callback)
router.callback_query(F.data.startswith("correct:"))(registrations.correct_registration_callback)
router.message(RegistrationState.waiting_for_corrected_name)(registrations.finish_correct_user)
router.callback_query(F.data.startswith("reject:"))(registrations.reject_registration_callback)
router.callback_query(F.data.startswith("link:"))(registrations.link_registration_callback)
router.callback_query(F.data.startswith("linkto:"))(registrations.choose_link_target_callback)
router.callback_query(F.data.startswith("linkto_page:"))(
    registrations.choose_link_target_page_callback
)
