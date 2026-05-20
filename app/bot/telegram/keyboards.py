from app.bot.shared.keyboards.keyboards import InlineKbs, ReplyKbs

main_keyboard = ReplyKbs.main_tg()
main_admin_entry_keyboard = ReplyKbs.admin_main_entry_tg()
poll_menu_keyboard = ReplyKbs.poll_menu_tg()
admin_main_keyboard = ReplyKbs.admin_main_tg()
new_user_keyboard = ReplyKbs.new_user_tg()
betting_keyboard = ReplyKbs.betting_tg()
betting_current_keyboard = ReplyKbs.betting_current_tg()
betting_info_keyboard = ReplyKbs.betting_info_tg()
poker_keyboard = ReplyKbs.poker_tg()
poker_info_keyboard = ReplyKbs.poker_info_tg()
room_keyboard = ReplyKbs.room_tg()
room_admin_keyboard = ReplyKbs.room_admin_tg()
admin_room_keyboard = ReplyKbs.admin_room_tg()
admin_room_correct_keyboard = ReplyKbs.admin_room_correct_tg()
played_before_keyboard = InlineKbs.played_before_tg
betting_tournament_keyboard = InlineKbs.betting_tournament_tg
betting_size_keyboard = InlineKbs.betting_size_tg
betting_player_keyboard = InlineKbs.betting_player_tg
betting_confirm_keyboard = InlineKbs.betting_confirm_tg
betting_stat_indicators_keyboard = InlineKbs.betting_stat_indicators_tg
betting_stat_mode_keyboard = InlineKbs.betting_stat_mode_tg
poker_stat_indicators_keyboard = InlineKbs.poker_stat_indicators_tg
stat_year_keyboard = InlineKbs.stat_year_tg
stat_sort_keyboard = InlineKbs.stat_sort_tg
poker_history_year_keyboard = InlineKbs.poker_history_year_tg
poker_history_dates_keyboard = InlineKbs.poker_history_dates_tg
poll_month_keyboard = InlineKbs.poll_month_tg
poll_admin_choose_keyboard = InlineKbs.poll_admin_choose_tg
poll_admin_other_keyboard = InlineKbs.poll_admin_other_tg
registration_optional_details_keyboard = InlineKbs.registration_optional_details_tg
registration_platform_keyboard = InlineKbs.registration_platform_tg
registration_review_keyboard = InlineKbs.registration_review_tg
registration_link_review_keyboard = InlineKbs.registration_link_review_tg
link_candidates_keyboard = InlineKbs.link_candidates_tg
link_candidates_page_keyboard = InlineKbs.link_candidates_tg_page
make_admin_candidates_keyboard = InlineKbs.make_admin_candidates_tg
poker_params_keyboard = InlineKbs.poker_params_tg
poker_add_player_candidates_keyboard = InlineKbs.poker_add_player_candidates_tg
poker_cashier_candidates_keyboard = InlineKbs.poker_cashier_candidates_tg
poker_room_admin_status_keyboard = InlineKbs.poker_room_admin_status_tg
poker_room_manage_player_keyboard = InlineKbs.poker_room_manage_player_tg
poker_room_approve_keyboard = InlineKbs.poker_room_approve_tg
poker_remove_player_candidates_keyboard = InlineKbs.poker_remove_player_candidates_tg
poker_unban_player_candidates_keyboard = InlineKbs.poker_unban_player_candidates_tg
poker_buyin_candidates_keyboard = InlineKbs.poker_buyin_candidates_tg
poker_buyin_count_keyboard = InlineKbs.poker_buyin_count_tg
poker_buyin_correct_confirm_keyboard = InlineKbs.poker_buyin_correct_confirm_tg
poker_cashout_candidates_keyboard = InlineKbs.poker_cashout_candidates_tg
poker_calc_keyboard = InlineKbs.poker_calc_tg
registration_candidates_keyboard = InlineKbs.registration_candidates_tg
registration_candidates_page_keyboard = InlineKbs.registration_candidates_tg_page


def main_dynamic_keyboard(*, is_admin: bool, has_active_poker: bool, has_active_poll: bool):
  return ReplyKbs.main_dynamic_tg(
    is_admin=is_admin,
    has_active_poker=has_active_poker,
    has_active_poll=has_active_poll,
  )
