from app.bot.shared.keyboards.keyboards import InlineKbs, ReplyKbs

main_keyboard = ReplyKbs.main_vk()
main_admin_entry_keyboard = ReplyKbs.admin_main_entry_vk()
poll_menu_keyboard = ReplyKbs.poll_menu_vk()
main_info_keyboard = ReplyKbs.main_info_vk()
admin_main_keyboard = ReplyKbs.admin_main_vk()
new_user_keyboard = ReplyKbs.new_user_vk()
betting_keyboard = ReplyKbs.betting_vk()
betting_current_keyboard = ReplyKbs.betting_current_vk()
betting_info_keyboard = ReplyKbs.betting_info_vk()
poker_keyboard = ReplyKbs.poker_vk()
poker_info_keyboard = ReplyKbs.poker_info_vk()
room_keyboard = ReplyKbs.room_vk()
room_admin_keyboard = ReplyKbs.room_admin_vk()
admin_room_keyboard = ReplyKbs.admin_room_vk()
admin_room_correct_keyboard = ReplyKbs.admin_room_correct_vk()
played_before_keyboard = InlineKbs.played_before_vk
betting_tournament_keyboard = InlineKbs.betting_tournament_vk
betting_size_keyboard = InlineKbs.betting_size_vk
betting_player_keyboard = InlineKbs.betting_player_vk
betting_confirm_keyboard = InlineKbs.betting_confirm_vk
betting_stat_indicators_keyboard = InlineKbs.betting_stat_indicators_vk
betting_stat_mode_keyboard = InlineKbs.betting_stat_mode_vk
poker_stat_indicators_keyboard = InlineKbs.poker_stat_indicators_vk
stat_year_keyboard = InlineKbs.stat_year_vk
stat_sort_keyboard = InlineKbs.stat_sort_vk
poker_history_year_keyboard = InlineKbs.poker_history_year_vk
poker_history_dates_keyboard = InlineKbs.poker_history_dates_vk
poll_month_keyboard = InlineKbs.poll_month_vk
poll_admin_choose_keyboard = InlineKbs.poll_admin_choose_vk
poll_admin_other_keyboard = InlineKbs.poll_admin_other_vk
registration_optional_details_keyboard = InlineKbs.registration_optional_details_vk
registration_platform_keyboard = InlineKbs.registration_platform_vk
registration_review_keyboard = InlineKbs.registration_review_vk
registration_link_review_keyboard = InlineKbs.registration_link_review_vk
link_candidates_keyboard = InlineKbs.link_candidates_vk
make_admin_candidates_keyboard = InlineKbs.make_admin_candidates_vk
poker_params_keyboard = InlineKbs.poker_params_vk
poker_add_player_candidates_keyboard = InlineKbs.poker_add_player_candidates_vk
poker_cashier_candidates_keyboard = InlineKbs.poker_cashier_candidates_vk
poker_room_admin_status_keyboard = InlineKbs.poker_room_admin_status_vk
poker_room_manage_player_keyboard = InlineKbs.poker_room_manage_player_vk
poker_room_approve_keyboard = InlineKbs.poker_room_approve_vk
poker_remove_player_candidates_keyboard = InlineKbs.poker_remove_player_candidates_vk
poker_unban_player_candidates_keyboard = InlineKbs.poker_unban_player_candidates_vk
poker_buyin_candidates_keyboard = InlineKbs.poker_buyin_candidates_vk
poker_buyin_count_keyboard = InlineKbs.poker_buyin_count_vk
poker_buyin_correct_confirm_keyboard = InlineKbs.poker_buyin_correct_confirm_vk
poker_cashout_candidates_keyboard = InlineKbs.poker_cashout_candidates_vk
poker_calc_keyboard = InlineKbs.poker_calc_vk
registration_candidates_keyboard = InlineKbs.registration_candidates_vk
registration_candidates_page_keyboard = InlineKbs.registration_candidates_vk_page
link_candidates_page_keyboard = InlineKbs.link_candidates_vk_page


def main_dynamic_keyboard(*, is_admin: bool, has_active_poker: bool, has_active_poll: bool) -> str:
  return ReplyKbs.main_dynamic_vk(
    is_admin=is_admin,
    has_active_poker=has_active_poker,
    has_active_poll=has_active_poll,
  )


def betting_dynamic_keyboard(*, include_make_bet: bool) -> str:
  return ReplyKbs.betting_dynamic_vk(include_make_bet=include_make_bet)
