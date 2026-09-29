"""Freeze the source-level VK dispatch sequence in each public route."""

import ast
from pathlib import Path

import pytest

ROUTING_DIR = Path(__file__).resolve().parents[1] / "app/bot/vk/handlers"
EXPECTED_DISPATCH = {
    "admin:handle_message_event": [
        "registrations.handle_approve_event",
        "registrations.handle_reject_event",
        "bets.handle_bet_receipt_actions_event",
        "registrations.handle_correct_event",
        "registrations.handle_link_event",
        "registrations.handle_link_to_event",
        "registrations.handle_link_page_event",
        "registrations.handle_make_admin_select_event",
        "start_poker.handle_poker_start_param_event",
        "players.handle_poker_add_player_select_event",
        "players.handle_poker_add_player_new_event",
        "players.handle_poker_add_player_cancel_event",
        "players.handle_poker_room_manage_select_event",
        "players.handle_poker_room_approve_select_event",
        "players.handle_poker_room_reject_select_event",
        "players.handle_poker_remove_player_select_event",
        "players.handle_poker_unban_player_select_event",
        "cashier.handle_poker_set_cashier_select_event",
        "cashier.handle_poker_room_set_cashier_select_event",
        "buyins.handle_poker_buyin_select_event",
        "buyins.handle_poker_buyin_correct_select_event",
        "buyins.handle_buyin_correction_confirmation_event",
        "buyins.handle_poker_buyin_count_select_event",
        "buyins.handle_poker_buyin_cancel_event",
        "cashier.handle_poker_cashout_select_event",
        "polls.handle_polladmin_other_event",
        "polls.handle_polladmin_month_event",
        "polls.handle_polladmin_cancel_event",
        "chips.handle_poker_calc_run_event",
        "poker.handle_poker_start_betting_inline_event",
    ],
    "admin:handle_admin_text_commands": [
        "registrations.handle_admin_corrected_name_text",
        "players.handle_admin_new_player_name_text",
        "buyins.handle_admin_buyin_correct_amount_text",
        "cashier.handle_admin_cashout_amount_text",
        "registrations.handle_approve_command_text",
        "registrations.handle_correct_command_text",
        "registrations.handle_reject_command_text",
        "registrations.handle_link_command_text",
        "management.handle_admin_main_make_admin_text",
        "start_poker.handle_admin_main_start_poker_text",
        "finish_poker.handle_admin_room_finish_poker_text",
        "chips.handle_admin_room_calculate_poker_text",
        "start_betting.handle_admin_room_start_betting_text",
        "polls.handle_admin_main_create_poll_text",
        "poker.handle_admin_room_correct_poker_text",
        "poker.handle_admin_room_correct_to_admin_room_text",
        "players.handle_add_player_text",
        "players.handle_remove_player_text",
        "players.handle_admin_room_unban_player_text",
        "cashier.handle_set_cashier_text",
        "buyins.handle_buyin_menu_text",
        "poker.handle_admin_room_to_room_text",
    ],
    "user:handle_user_message_event": [
        "polls.handle_poll_noop_event",
        "polls.handle_poll_month_event",
        "polls.handle_poll_page_event",
        "polls.handle_poll_day_event",
        "polls.handle_poll_suggest_event",
        "polls.handle_poll_done_event",
        "polls.handle_poll_cancel_event",
        "poker_stats.handle_pokerhist_cancel_event",
        "poker_stats.handle_pokerhistyear_event",
        "poker_stats.handle_pokerhistpage_event",
        "poker_stats.handle_pokerhistdate_event",
        "registration.handle_registration_existing_event",
        "registration.handle_registration_played_before_event",
        "registration.handle_registration_existing_page_event",
        "registration.handle_registration_new_name_event",
        "registration.handle_registration_platform_event",
        "registration.handle_registration_optional_bank_event",
        "registration.handle_registration_optional_phone_event",
        "registration.handle_registration_optional_skip_event",
        "bets.handle_bet_tournament_event",
        "bets.handle_bet_size_event",
        "bets.handle_bet_winner_event",
        "bets.handle_bet_loser_event",
        "bets.handle_bet_confirmation_event",
        "betting_stats.handle_betstat_page_event",
        "betting_stats.handle_betstat_toggle_event",
        "betting_stats.handle_betting_tournament_actions_event",
        "betting_stats.handle_betstat_back_event",
        "poker_stats.handle_pokerstat_page_event",
        "poker_stats.handle_pokerstat_toggle_event",
        "poker_stats.handle_pokerstat_done_event",
        "poker_stats.handle_pokerstat_sort_page_event",
        "poker_stats.handle_pokerstat_sort_event",
        "poker_stats.handle_pokerstat_sort_done_event",
        "poker_stats.handle_pokerstat_sort_cancel_event",
        "poker_stats.handle_poker_stat_year_actions_event",
        "poker_stats.handle_pokerstat_cancel_event",
        "betting_stats.handle_betstat_done_event",
        "betting_stats.handle_betstat_sort_page_event",
        "betting_stats.handle_betstat_sort_event",
        "betting_stats.handle_betstat_sort_done_event",
        "betting_stats.handle_betstat_sort_back_event",
        "betting_stats.handle_betstat_sort_cancel_event",
        "betting_stats.handle_betstat_cancel_event",
    ],
    "user:handle_user_message_new": [
        "poker.handle_chips_input_text",
        "navigation.handle_navigation_access_check_text",
        "navigation.handle_main_admin_text",
        "navigation.handle_admin_main_to_main_text",
        "navigation.handle_main_betting_text",
        "navigation.handle_main_info_text",
        "navigation.handle_main_next_poker_date_text",
        "navigation.handle_main_poker_text",
        "navigation.handle_betting_to_main_text",
        "navigation.handle_poker_to_main_text",
        "navigation.handle_room_to_main_text",
        "navigation.handle_poll_menu_to_main_text",
        "navigation.handle_poker_info_text",
        "navigation.handle_betting_info_text",
        "navigation.handle_main_info_to_main_text",
        "information.handle_bettinginfo_betting_rules_text",
        "information.handle_bettinginfo_betting_stat_info_text",
        "information.handle_bettinginfo_betting_ach_info_text",
        "information.handle_pokerinfo_poker_stat_info_text",
        "information.handle_pokerinfo_poker_ach_info_text",
        "poker_stats.handle_poker_history_text",
        "poker_stats.handle_poker_poker_stat_text",
        "betting_stats.handle_betting_betting_stat_text",
        "bets.handle_make_bet_text",
        "bets.handle_betting_pay_bet_text",
        "bets.handle_bet_amount_text",
        "bets.handle_bet_payment_receipt_text",
        "poker.handle_main_room_text",
        "poker.handle_room_poker_admin_text",
        "polls.handle_poker_poll_text",
        "polls.handle_poll_menu_results_text",
        "poker.handle_room_status_text",
        "registration.handle_new_user_registration_text",
        "registration.handle_new_user_about_text",
        "polls.handle_poll_custom_day_text",
        "registration.handle_played_before_text",
        "registration.handle_new_name_text",
        "registration.handle_optional_bank_text",
        "registration.handle_optional_phone_text",
        "registration.handle_optional_details_action_text",
    ],
}


def _dispatch_calls(side: str, entrypoint: str) -> list[str]:
    tree = ast.parse((ROUTING_DIR / side / "routing.py").read_text())
    route = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == entrypoint
    )
    calls = []
    for node in ast.walk(route):
        if not isinstance(node, ast.Await) or not isinstance(node.value, ast.Call):
            continue
        target = node.value.func
        if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name):
            if target.value.id in {
                "bets",
                "betting_stats",
                "buyins",
                "cashier",
                "chips",
                "finish_poker",
                "information",
                "management",
                "navigation",
                "players",
                "poker",
                "poker_stats",
                "polls",
                "registration",
                "start_betting",
                "start_poker",
                "registrations",
            }:
                calls.append((node.lineno, f"{target.value.id}.{target.attr}"))
    return [name for _, name in sorted(calls)]


@pytest.mark.parametrize("route", EXPECTED_DISPATCH)
def test_vk_dispatch_order(route: str) -> None:
    side, entrypoint = route.split(":")
    assert _dispatch_calls(side, entrypoint) == EXPECTED_DISPATCH[route]
