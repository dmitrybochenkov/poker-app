from fastapi.responses import PlainTextResponse

from app.bot.vk.state import durable_vk_workflow

from . import bets, betting_stats, information, navigation, poker, poker_stats, polls, registration
from .common import HANDLER_UNMATCHED


@durable_vk_workflow
async def handle_user_message_event(event_object: dict) -> PlainTextResponse | None:
    user_id = event_object.get("user_id")
    peer_id = event_object.get("peer_id")
    event_id = event_object.get("event_id")
    conversation_message_id = event_object.get("conversation_message_id")
    callback_payload = event_object.get("payload") or {}
    action = callback_payload.get("action")
    if not user_id or not peer_id or not event_id:
        return PlainTextResponse("ok")
    result = await polls.handle_poll_noop_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_month_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_day_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_suggest_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_done_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerhist_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerhistyear_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerhistpage_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerhistdate_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_existing_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_played_before_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_existing_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_new_name_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_platform_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_optional_bank_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_optional_phone_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_registration_optional_skip_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_tournament_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_size_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_winner_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_loser_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_confirmation_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_toggle_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betting_tournament_actions_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_back_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_toggle_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_done_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_sort_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_sort_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_sort_done_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_sort_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_poker_stat_year_actions_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_pokerstat_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_done_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_sort_page_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_sort_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_sort_done_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_sort_back_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_sort_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betstat_cancel_event(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    return None


@durable_vk_workflow
async def handle_user_message_new(
    *, user_id: int, text: str, raw_message: dict | None = None
) -> PlainTextResponse | None:
    result = await poker.handle_chips_input_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_navigation_access_check_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_admin_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_admin_main_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_betting_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_next_poker_date_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_poker_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_betting_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_poker_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_room_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_poll_menu_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_poker_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_betting_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation.handle_main_info_to_main_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information.handle_bettinginfo_betting_rules_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information.handle_bettinginfo_betting_stat_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information.handle_bettinginfo_betting_ach_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information.handle_pokerinfo_poker_stat_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information.handle_pokerinfo_poker_ach_info_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_poker_history_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats.handle_poker_poker_stat_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats.handle_betting_betting_stat_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_make_bet_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_betting_pay_bet_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_amount_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_payment_receipt_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_main_room_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_room_poker_admin_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poker_poll_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_menu_results_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_room_status_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_new_user_registration_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_new_user_about_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_poll_custom_day_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_played_before_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_new_name_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_optional_bank_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_optional_phone_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration.handle_optional_details_action_text(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    return None
