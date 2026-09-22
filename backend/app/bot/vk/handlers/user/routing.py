from fastapi.responses import PlainTextResponse

from . import bets, betting_stats, information, navigation, poker, poker_stats, polls, registration
from .common import HANDLER_UNMATCHED


async def handle_user_message_event(event_object: dict) -> PlainTextResponse | None:
    user_id = event_object.get("user_id")
    peer_id = event_object.get("peer_id")
    event_id = event_object.get("event_id")
    conversation_message_id = event_object.get("conversation_message_id")
    callback_payload = event_object.get("payload") or {}
    action = callback_payload.get("action")
    if not user_id or not peer_id or not event_id:
        return PlainTextResponse("ok")
    result = await polls._event_0_00(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_01(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_02(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_03(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_04(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_05(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._event_0_06(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_07(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_08(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_09(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_10(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_11(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_12(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_13(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_14(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_15(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_16(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_17(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._event_0_18(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._event_0_19(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._event_0_20(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._event_0_21(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._event_0_22(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._event_0_23(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_24(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_25(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_26(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_27(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_28(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_29(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_30(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_31(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_32(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_33(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_34(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_35(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._event_0_36(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_37(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_38(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_39(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_40(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_41(
        user_id=user_id,
        peer_id=peer_id,
        event_id=event_id,
        conversation_message_id=conversation_message_id,
        callback_payload=callback_payload,
        action=action,
    )
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._event_0_42(
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


async def handle_user_message_new(
    *, user_id: int, text: str, raw_message: dict | None = None
) -> PlainTextResponse | None:
    result = await poker._text_1_00(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_01(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_02(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_03(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_04(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_05(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_06(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_07(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_08(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_09(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_10(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_11(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_12(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_13(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await navigation._text_1_14(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information._text_1_15(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information._text_1_16(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information._text_1_17(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information._text_1_18(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await information._text_1_19(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._text_1_20(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker_stats._text_1_21(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._text_1_22(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._text_1_23(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._text_1_24(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await betting_stats._text_1_25(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._text_1_26(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._text_1_27(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._text_1_28(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await bets._text_1_29(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_30(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_31(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._text_1_32(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._text_1_33(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await poker._text_1_34(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_35(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_36(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await polls._text_1_37(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_38(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_39(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_40(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_41(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    result = await registration._text_1_42(user_id=user_id, text=text, raw_message=raw_message)
    if result is not HANDLER_UNMATCHED:
        return result
    return None
