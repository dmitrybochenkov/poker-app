from fastapi.responses import PlainTextResponse

from . import (
    bets,
    buyins,
    cashier,
    chips,
    finish_poker,
    management,
    players,
    poker,
    polls,
    registrations,
    start_betting,
    start_poker,
)
from .common import HANDLER_UNMATCHED


async def handle_message_event(event_object: dict) -> PlainTextResponse | None:
    admin_user_id = event_object.get("user_id")
    peer_id = event_object.get("peer_id")
    event_id = event_object.get("event_id")
    conversation_message_id = event_object.get("conversation_message_id")
    callback_payload = event_object.get("payload") or {}
    action = callback_payload.get("action")

    if not admin_user_id or not peer_id or not event_id:
        return None
    result = await registrations.handle_approve_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_reject_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets.handle_bet_receipt_actions_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_correct_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_link_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_link_to_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_link_page_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_make_admin_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await start_poker.handle_poker_start_param_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_add_player_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_add_player_new_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_add_player_cancel_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_room_manage_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_room_approve_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_room_reject_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_remove_player_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_poker_unban_player_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier.handle_poker_set_cashier_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier.handle_poker_room_set_cashier_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_poker_buyin_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_poker_buyin_correct_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_buyin_correction_confirmation_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_poker_buyin_count_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_poker_buyin_cancel_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier.handle_poker_cashout_select_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_polladmin_other_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_polladmin_month_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_polladmin_cancel_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await chips.handle_poker_calc_run_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_poker_start_betting_inline_event(
        admin_user_id=admin_user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
        handle_admin_text_commands=handle_admin_text_commands,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    return None


async def handle_admin_text_commands(*, user_id: int, text: str) -> PlainTextResponse | None:
    result = await registrations.handle_admin_corrected_name_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_admin_new_player_name_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_admin_buyin_correct_amount_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier.handle_admin_cashout_amount_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_approve_command_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_correct_command_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_reject_command_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations.handle_link_command_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await management.handle_admin_main_make_admin_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await start_poker.handle_admin_main_start_poker_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await finish_poker.handle_admin_room_finish_poker_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await chips.handle_admin_room_calculate_poker_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await start_betting.handle_admin_room_start_betting_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls.handle_admin_main_create_poll_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_admin_room_correct_poker_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_admin_room_correct_to_admin_room_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_add_player_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_remove_player_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players.handle_admin_room_unban_player_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier.handle_set_cashier_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins.handle_buyin_menu_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker.handle_admin_room_to_room_text(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    return None
