from types import SimpleNamespace
from unittest.mock import ANY, AsyncMock, Mock, call

import pytest

from app.bot.shared.texts.inline.telegram.admin import poker as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import cashier as tg_poker


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


def _message():
    return SimpleNamespace(from_user=SimpleNamespace(id=99), answer=AsyncMock())


def _callback(data="pokercashier:7"):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=99),
        data=data,
        answer=AsyncMock(),
    )


def _patch_session(monkeypatch):
    monkeypatch.setattr(tg_poker, "SessionFactory", _Session)


@pytest.mark.asyncio
async def test_cashier_menu_stops_when_admin_authorization_fails(monkeypatch):
    _patch_session(monkeypatch)
    ensure_admin = AsyncMock(return_value=False)
    use_case = Mock()
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_message", ensure_admin)
    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", use_case)
    message = _message()

    await tg_poker.set_cashier_menu(message)

    ensure_admin.assert_awaited_once_with(session=ANY, user_id=99, message=message)
    use_case.assert_not_called()
    message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_cashier_menu_reports_no_active_players(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_message", AsyncMock(return_value=True))
    use_case = SimpleNamespace(list_active_poker_players=AsyncMock(return_value=[]))
    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(tg_poker, "PokerRepository", Mock())
    monkeypatch.setattr(tg_poker, "PokerDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "BuyinDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "UserRepository", Mock())
    message = _message()

    await tg_poker.set_cashier_menu(message)

    message.answer.assert_awaited_once_with(Text.admin.POKER_PLAYERS_EMPTY.value)


@pytest.mark.asyncio
async def test_cashier_menu_filters_missing_users_and_preserves_candidate_order(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_message", AsyncMock(return_value=True))
    active_players = [
        SimpleNamespace(player_id=3, player_name="Third"),
        SimpleNamespace(player_id=2, player_name="Missing"),
        SimpleNamespace(player_id=1, player_name="First"),
    ]
    use_case = SimpleNamespace(list_active_poker_players=AsyncMock(return_value=active_players))
    users = {
        3: SimpleNamespace(row_id=3),
        2: None,
        1: SimpleNamespace(row_id=1),
    }
    user_repository = SimpleNamespace(
        get_by_row_id=AsyncMock(side_effect=lambda row_id: users[row_id])
    )
    keyboard = object()
    keyboard_factory = Mock(return_value=keyboard)
    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(tg_poker, "PokerRepository", Mock())
    monkeypatch.setattr(tg_poker, "PokerDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "BuyinDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "UserRepository", lambda session: user_repository)
    monkeypatch.setattr(tg_poker, "poker_cashier_candidates_keyboard", keyboard_factory)
    message = _message()

    await tg_poker.set_cashier_menu(message)

    assert user_repository.get_by_row_id.await_args_list == [call(3), call(2), call(1)]
    candidates = keyboard_factory.call_args.kwargs["players"]
    assert [(item.player_id, item.player_name) for item in candidates] == [
        (3, "Third"),
        (1, "First"),
    ]
    message.answer.assert_awaited_once_with(
        Text.admin.POKER_CASHIER_CHOOSE.value,
        reply_markup=keyboard,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("handler_name", "expected_text", "keyboard_name"),
    [
        (
            "open_correct_poker_menu",
            InlineText.OPEN_CORRECT_POKER_MENU_TEXT_01,
            "admin_room_correct_keyboard",
        ),
        (
            "back_from_correct_poker_menu",
            Text.admin.ADMIN_PANEL.value,
            "admin_room_keyboard",
        ),
    ],
)
async def test_correction_navigation_preserves_text_and_keyboard(
    monkeypatch, handler_name, expected_text, keyboard_name
):
    _patch_session(monkeypatch)
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_message", AsyncMock(return_value=True))
    message = _message()

    await getattr(tg_poker, handler_name)(message)

    message.answer.assert_awaited_once_with(
        expected_text,
        reply_markup=getattr(tg_poker, keyboard_name),
    )


@pytest.mark.asyncio
async def test_cashier_callback_parses_user_id_mutates_and_refreshes_room(monkeypatch):
    _patch_session(monkeypatch)
    events = []
    monkeypatch.setattr(tg_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_callback", AsyncMock(return_value=True))
    use_case = SimpleNamespace(
        set_cashier_for_active_poker=AsyncMock(
            side_effect=lambda **kwargs: (
                events.append(("mutation", kwargs["cashier_id"])) or object()
            )
        )
    )
    user_repository = SimpleNamespace(
        get_by_row_id=AsyncMock(return_value=SimpleNamespace(name="Cashier"))
    )

    async def refresh(*, session):
        events.append(("refresh", session))

    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(tg_poker, "PokerRepository", Mock())
    monkeypatch.setattr(tg_poker, "PokerDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "BuyinDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "UserRepository", lambda session: user_repository)
    monkeypatch.setattr(tg_poker, "_refresh_admin_room_status", refresh)
    callback = _callback("pokercashier:42")

    await tg_poker.set_cashier_callback(callback)

    use_case.set_cashier_for_active_poker.assert_awaited_once_with(cashier_id=42)
    assert events[0] == ("mutation", 42)
    assert events[1][0] == "refresh"
    callback.answer.assert_awaited_once_with(
        f"Cashier{InlineText.SET_CASHIER_CALLBACK_TEXT_01_PART_1}"
    )


@pytest.mark.asyncio
async def test_cashier_callback_stops_when_callback_authorization_fails(monkeypatch):
    _patch_session(monkeypatch)
    clear = AsyncMock()
    ensure_admin = AsyncMock(return_value=False)
    use_case = Mock()
    monkeypatch.setattr(tg_poker, "_clear_inline_keyboard", clear)
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_callback", ensure_admin)
    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", use_case)
    callback = _callback("pokercashier:42")

    await tg_poker.set_cashier_callback(callback)

    clear.assert_awaited_once_with(callback)
    ensure_admin.assert_awaited_once_with(session=ANY, user_id=99, callback=callback)
    use_case.assert_not_called()
    callback.answer.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("active", "expected_text"),
    [
        (None, Text.admin.POKER_ACTIVE_NOT_FOUND.value),
        (
            (SimpleNamespace(cashier_id=5), object()),
            InlineText.SET_CASHIER_FROM_ROOM_CALLBACK_TEXT_01,
        ),
    ],
)
async def test_room_cashier_callback_preserves_missing_and_existing_cashier_guards(
    monkeypatch, active, expected_text
):
    _patch_session(monkeypatch)
    monkeypatch.setattr(tg_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_callback", AsyncMock(return_value=True))
    poker_repository = SimpleNamespace(get_started=AsyncMock(return_value=active))
    monkeypatch.setattr(tg_poker, "PokerRepository", lambda session: poker_repository)
    callback = _callback("pokerroomcashier:42")

    await tg_poker.set_cashier_from_room_callback(callback)

    callback.answer.assert_awaited_once_with(expected_text, show_alert=True)


@pytest.mark.asyncio
async def test_room_cashier_callback_refreshes_status_after_success(monkeypatch):
    _patch_session(monkeypatch)
    monkeypatch.setattr(tg_poker, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_poker, "_ensure_tg_admin_callback", AsyncMock(return_value=True))
    poker_repository = SimpleNamespace(
        get_started=AsyncMock(return_value=(SimpleNamespace(cashier_id=None), object()))
    )
    use_case = SimpleNamespace(set_cashier_for_active_poker=AsyncMock(return_value=object()))
    user_repository = SimpleNamespace(
        get_by_row_id=AsyncMock(return_value=SimpleNamespace(name="Room Cashier"))
    )
    refresh = AsyncMock()
    monkeypatch.setattr(tg_poker, "PokerRepository", lambda session: poker_repository)
    monkeypatch.setattr(tg_poker, "PokerDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "BuyinDataRepository", Mock())
    monkeypatch.setattr(tg_poker, "ManagePokerPlayersUseCase", lambda **kwargs: use_case)
    monkeypatch.setattr(tg_poker, "UserRepository", lambda session: user_repository)
    monkeypatch.setattr(tg_poker, "_refresh_admin_room_status", refresh)
    callback = _callback("pokerroomcashier:42")

    await tg_poker.set_cashier_from_room_callback(callback)

    use_case.set_cashier_for_active_poker.assert_awaited_once_with(cashier_id=42)
    refresh.assert_awaited_once_with(session=ANY)
    callback.answer.assert_awaited_once_with(
        f"Room Cashier{InlineText.SET_CASHIER_FROM_ROOM_CALLBACK_TEXT_02_PART_1}"
    )
