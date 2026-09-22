from fastapi.responses import PlainTextResponse

from app.application.use_cases.poker.manage_players import ManagePokerPlayersUseCase
from app.bot.shared.buttons.buttons import Buttons
from app.bot.shared.chips_runtime import (
    VK_ADMIN_CHIPS_STATUS_MSG_IDS,
    VK_USER_CHIPS_RESULT_MSG_IDS,
)
from app.bot.shared.texts.inline.vk.user import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.keyboards import (
    poker_room_approve_keyboard as tg_poker_room_approve_keyboard,
)
from app.bot.vk.api import (
    delete_vk_message_by_id,
    send_vk_message,
    send_vk_message_with_id,
)
from app.bot.vk.keyboards import (
    admin_room_keyboard,
    new_user_keyboard,
    poker_calc_keyboard,
    poker_cashout_candidates_keyboard,
    poker_room_approve_keyboard,
    room_admin_keyboard,
    room_keyboard,
)
from app.bot.vk.state import (
    vk_user_contexts,
)
from app.db.repositories.bet_repository import BetRepository
from app.db.repositories.poker_data_repository import PokerDataRepository
from app.db.repositories.poker_repository import PokerRepository
from app.db.repositories.poker_room_denied_repository import PokerRoomDeniedRepository
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

from .common import (
    HANDLER_UNMATCHED,
    _build_chips_status_text,
    _build_user_chips_text,
    _chips_reaction,
    _get_vk_user,
    _money_kopecks_from_chips,
    _notify_admins_about_room_join,
)


async def handle_chips_input_text(*, user_id, text, raw_message):
    if text.isdigit():
        chips = int(text)
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None or not user.is_approved:
                return None
            ready = await PokerRepository(session).get_latest_ready_for_chips_with_params()
            if ready is None:
                return None
            poker, params = ready
            bb_size = max(1, int(params.bb_size_chips or 10))
            step = max(1, bb_size // 2)
            if chips % step != 0:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_INVALID.value.format(step=step)
                )
                return PlainTextResponse("ok")
            poker_data_repository = PokerDataRepository(session)
            players = await poker_data_repository.list_players(date=poker.date)
            if not players:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_READY.value
                )
                return PlainTextResponse("ok")
            if user.is_admin:
                vk_user_contexts.setdefault(user_id, {})["cashout_input_value"] = str(chips)
                await send_vk_message(
                    user_id=user_id,
                    message=Text.admin.POKER_CHIPS_FOR_WHO.value.format(chips=chips),
                    keyboard=poker_cashout_candidates_keyboard(players=players),
                )
                return PlainTextResponse("ok")
            player = await poker_data_repository.get_player(
                date=poker.date, player_id=int(user.row_id)
            )
            if player is None:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_IN_GAME.value
                )
                return PlainTextResponse("ok")
            money_kopecks = _money_kopecks_from_chips(
                chips=chips,
                buyins=int(player.buyins),
                buyin_size_chips=int(params.buyin_size_chips),
                buyin_size_kopecks=int(params.buyin_size_kopecks),
            )
            updated = await poker_data_repository.set_chips(
                date=poker.date, player_id=int(user.row_id), chips=chips
            )
            if updated is None:
                await send_vk_message(
                    user_id=user_id, message=Text.user.FINISH_CHIPS_NOT_IN_GAME.value
                )
                return PlainTextResponse("ok")
            await poker_data_repository.set_cashout(
                date=poker.date,
                player_id=int(user.row_id),
                money_kopecks=int(money_kopecks),
            )
            all_players = await poker_data_repository.list_players(date=poker.date)
            player_row_ids = {int(p.player_id) for p in all_players}
            admins = [
                u
                for u in await user_repository.list_approved()
                if u.is_admin and int(u.row_id) in player_row_ids
            ]
            chips_in_game = sum(int(p.buyins) * int(params.buyin_size_chips) for p in all_players)
            chips_entered = sum(int(p.chips or 0) for p in all_players)
            for p in all_players:
                setattr(p, "_buyin_size_chips", int(params.buyin_size_chips))
                setattr(p, "_buyin_size_kopecks", int(params.buyin_size_kopecks))
            admin_text = _build_chips_status_text(
                players=all_players,
                chips_in_game=chips_in_game,
                chips_entered=chips_entered,
            )
            from app.bot.telegram.runtime import telegram_bot

            for admin in admins:
                if (
                    admin.notification_platform == "tg"
                    and admin.telegram_id is not None
                    and telegram_bot is not None
                ):
                    await telegram_bot.send_message(chat_id=admin.telegram_id, text=admin_text)
                elif admin.notification_platform == "vk" and admin.vk_id is not None:
                    prev_mid = VK_ADMIN_CHIPS_STATUS_MSG_IDS.get(int(admin.vk_id))
                    if prev_mid is not None:
                        try:
                            await delete_vk_message_by_id(
                                peer_id=int(admin.vk_id), message_id=int(prev_mid)
                            )
                        except Exception:
                            pass
                    sent_mid = await send_vk_message_with_id(
                        user_id=int(admin.vk_id),
                        message=admin_text,
                        keyboard=poker_calc_keyboard(),
                    )
                    if sent_mid is not None:
                        VK_ADMIN_CHIPS_STATUS_MSG_IDS[int(admin.vk_id)] = int(sent_mid)
            user_text = _build_user_chips_text(
                chips=int(chips),
                money_kopecks=int(money_kopecks),
                reaction=_chips_reaction(int(money_kopecks)),
            )
            prev_user_mid = VK_USER_CHIPS_RESULT_MSG_IDS.get(int(user_id))
            if prev_user_mid is not None:
                try:
                    await delete_vk_message_by_id(
                        peer_id=int(user_id), message_id=int(prev_user_mid)
                    )
                except Exception:
                    pass
            sent_mid = await send_vk_message_with_id(user_id=user_id, message=user_text)
            if sent_mid is not None:
                VK_USER_CHIPS_RESULT_MSG_IDS[int(user_id)] = int(sent_mid)
            return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_main_room_text(*, user_id, text, raw_message):
    if text == Buttons.main.ROOM.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_NEED_REGISTRATION.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")
            if not user.is_approved:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_PENDING.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")

            poker_repository = PokerRepository(session)
            poker_data_repository = PokerDataRepository(session)
            active = await poker_repository.get_started()
            ready = await poker_repository.get_latest_ready_for_chips() if active is None else None
            current_poker_date = (
                active[0].date
                if active is not None
                else (ready.date if ready is not None else None)
            )
            if current_poker_date is None:
                await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
                return PlainTextResponse("ok")

            use_case = ManagePokerPlayersUseCase(
                poker_repository=poker_repository,
                poker_data_repository=poker_data_repository,
                poker_room_denied_repository=PokerRoomDeniedRepository(session),
            )
            is_denied = await use_case.is_denied_for_active_poker(user_row_id=int(user.row_id))
            if is_denied:
                await send_vk_message(
                    user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value
                )
                return PlainTextResponse("ok")
            players = await poker_data_repository.list_players(date=current_poker_date)
            if players:
                already_in_room = any(int(item.player_id) == int(user.row_id) for item in players)
                if already_in_room:
                    await send_vk_message(
                        user_id=user_id,
                        message=Text.user.ROOM_JOINED.value,
                        keyboard=room_admin_keyboard if user.is_admin else room_keyboard,
                    )
                    return PlainTextResponse("ok")

            if active is None:
                await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
                return PlainTextResponse("ok")
            poker, _ = active
            if poker.cashier_id is None:
                created = await use_case.add_player_to_active_poker(
                    player_id=int(user.row_id), player_name=user.name
                )
                if created is None:
                    await send_vk_message(
                        user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value
                    )
                    return PlainTextResponse("ok")
                await _notify_admins_about_room_join(
                    session=session,
                    joined_user=user,
                    platform_label="VK",
                )
            else:
                players_now = await poker_data_repository.list_players(date=poker.date)
                player_row_ids = {int(item.player_id) for item in players_now}
                approved = await user_repository.list_approved()
                admins = [
                    u
                    for u in approved
                    if u.is_admin
                    and int(u.row_id) in player_row_ids
                    and u.notification_platform == "vk"
                    and u.vk_id is not None
                ]
                for admin in admins:
                    await send_vk_message(
                        user_id=int(admin.vk_id),
                        message=f'{InlineText.TEXT_1_30_TEXT_01_PART_1}{user.name}{InlineText.TEXT_1_30_TEXT_01_PART_2}',
                        keyboard=poker_room_approve_keyboard(player_id=int(user.row_id)),
                    )
                from app.bot.telegram.runtime import telegram_bot

                tg_admins = [
                    u
                    for u in approved
                    if u.is_admin
                    and int(u.row_id) in player_row_ids
                    and u.notification_platform == "tg"
                    and u.telegram_id is not None
                ]
                if telegram_bot is not None:
                    for admin in tg_admins:
                        await telegram_bot.send_message(
                            chat_id=int(admin.telegram_id),
                            text=f'{InlineText.TEXT_1_30_TEXT_02_PART_1}{user.name}{InlineText.TEXT_1_30_TEXT_02_PART_2}',
                            reply_markup=tg_poker_room_approve_keyboard(player_id=int(user.row_id)),
                        )
                await send_vk_message(
                    user_id=user_id,
                    message=InlineText.TEXT_1_30_TEXT_03,
                )
                return PlainTextResponse("ok")

        await send_vk_message(
            user_id=user_id,
            message=Text.user.ROOM_JOINED.value,
            keyboard=room_admin_keyboard if user.is_admin else room_keyboard,
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_room_poker_admin_text(*, user_id, text, raw_message):
    if text == Buttons.room.POKER_ADMIN.value:
        user = await _get_vk_user(user_id)
        if user is None:
            await send_vk_message(
                user_id=user_id,
                message=Text.user.STATUS_NEED_REGISTRATION.value,
                keyboard=new_user_keyboard,
            )
            return PlainTextResponse("ok")
        if not user.is_approved:
            await send_vk_message(
                user_id=user_id, message=Text.user.STATUS_PENDING.value, keyboard=new_user_keyboard
            )
            return PlainTextResponse("ok")
        if not user.is_admin:
            await send_vk_message(
                user_id=user_id, message=Text.admin.NO_RIGHTS.value, keyboard=room_keyboard
            )
            return PlainTextResponse("ok")
        await send_vk_message(
            user_id=user_id, message=Text.admin.ADMIN_PANEL.value, keyboard=admin_room_keyboard
        )
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED


async def handle_room_status_text(*, user_id, text, raw_message):
    if text == Buttons.room.STATUS.value:
        async with SessionFactory() as session:
            user_repository = UserRepository(session)
            user = await user_repository.get_by_vk_id(user_id)
            if user is None:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_NEED_REGISTRATION.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")
            if not user.is_approved:
                await send_vk_message(
                    user_id=user_id,
                    message=Text.user.STATUS_PENDING.value,
                    keyboard=new_user_keyboard,
                )
                return PlainTextResponse("ok")

            use_case = ManagePokerPlayersUseCase(
                poker_repository=PokerRepository(session),
                poker_data_repository=PokerDataRepository(session),
            )
            players = await use_case.list_active_poker_players()
            if not players:
                await send_vk_message(user_id=user_id, message=Text.user.STATUS_ROOM_CLOSED.value)
                return PlainTextResponse("ok")

            current_player = next(
                (item for item in players if int(item.player_id) == int(user.row_id)), None
            )
            if current_player is None:
                await send_vk_message(
                    user_id=user_id, message=Text.user.STATUS_ROOM_NOT_ADDED.value
                )
                return PlainTextResponse("ok")

            lines: list[str] = [InlineText.TEXT_1_34_TEXT_01]
            if user.is_admin:
                active = await PokerRepository(session).get_started()
                bet_row_ids: set[int] = set()
                bet_name_by_id: dict[int, str] = {}
                better_row_by_id: dict[int, int] = {}
                if active is not None:
                    poker, _ = active
                    bets = await BetRepository(session).list_for_poker(date=poker.date)
                    for bet in bets:
                        better_id = int(bet.better_id)
                        better_user = await user_repository.get_by_row_id(better_id)
                        if better_user is not None:
                            better_row_id = int(better_user.row_id)
                            bet_row_ids.add(better_row_id)
                            better_row_by_id[better_id] = better_row_id
                        else:
                            # better_id in bets is expected to be users.row_id
                            bet_row_ids.add(better_id)
                            better_row_by_id[better_id] = better_id
                        bet_name_by_id[better_id] = bet.better_name
                player_ids = {int(p.player_id) for p in players}
                for p in players:
                    if int(p.player_id) in bet_row_ids:
                        lines.append(f'{p.player_name}{InlineText._TEXT_1_34_MARKER_01_PART_2}{p.buyins}')
                    else:
                        lines.append(f"{p.player_name}: {p.buyins}")
                outsider_ids = [
                    better_id
                    for better_id in bet_name_by_id.keys()
                    if better_row_by_id.get(better_id) not in player_ids
                ]
                outsider_ids.sort()
                for better_id in outsider_ids:
                    better_name = bet_name_by_id.get(better_id, f"ID {better_id}")
                    lines.append(f'{better_name}{InlineText._TEXT_1_34_MARKER_02_PART_2}')
            else:
                for p in players:
                    lines.append(f"{p.player_name}: {p.buyins}")

        await send_vk_message(user_id=user_id, message="\n".join(lines))
        return PlainTextResponse("ok")
    return HANDLER_UNMATCHED
