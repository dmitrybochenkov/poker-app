from fastapi.responses import PlainTextResponse

from . import bets, buyins, cashier, chips, management, players, poker, polls, registrations
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
    result = await registrations._event_0_00(
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
    result = await registrations._event_0_01(
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
    result = await bets._event_0_02(
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
    result = await registrations._event_0_03(
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
    result = await registrations._event_0_04(
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
    result = await registrations._event_0_05(
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
    result = await registrations._event_0_06(
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
    result = await registrations._event_0_07(
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
    result = await poker._event_0_08(
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
    result = await players._event_0_09(
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
    result = await players._event_0_10(
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
    result = await players._event_0_11(
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
    result = await players._event_0_12(
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
    result = await players._event_0_13(
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
    result = await players._event_0_14(
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
    result = await players._event_0_15(
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
    result = await players._event_0_16(
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
    result = await cashier._event_0_17(
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
    result = await cashier._event_0_18(
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
    result = await buyins._event_0_19(
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
    result = await buyins._event_0_20(
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
    result = await buyins._event_0_21(
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
    result = await buyins._event_0_22(
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
    result = await buyins._event_0_23(
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
    result = await cashier._event_0_24(
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
    result = await polls._event_0_25(
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
    result = await polls._event_0_26(
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
    result = await polls._event_0_27(
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
    result = await chips._event_0_28(
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
    result = await poker._event_0_29(
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
    result = await registrations._text_1_00(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players._text_1_01(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins._text_1_02(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier._text_1_03(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations._text_1_04(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations._text_1_05(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations._text_1_06(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registrations._text_1_07(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await management._text_1_08(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_09(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_10(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await chips._text_1_11(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._text_1_12(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._text_1_13(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_14(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_15(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players._text_1_16(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players._text_1_17(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await players._text_1_18(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await cashier._text_1_19(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await buyins._text_1_20(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_21(user_id=user_id, text=text)
    if result is not HANDLER_UNMATCHED:
        return result
    return None
