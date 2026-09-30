from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.shared.buttons.buttons import Buttons
from app.bot.telegram.handlers.user import bets as tg_bets
from app.bot.vk.handlers.user import bets as vk_bets


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False


class _State:
    set_state = AsyncMock()
    update_data = AsyncMock()


def _install_draft_fakes(monkeypatch, module, *, user):
    captured = {}

    class UserRepository:
        def __init__(self, session):
            pass

        async def get_by_telegram_id(self, external_id):
            captured["telegram_id"] = external_id
            return user

        async def get_by_vk_id(self, external_id):
            captured["vk_id"] = external_id
            return user

    class BetUseCases:
        def __init__(self, **kwargs):
            pass

        async def get_bet_draft_data(self, **kwargs):
            captured["draft_kwargs"] = kwargs
            return (
                SimpleNamespace(small_size_kopecks=10_000, big_size_kopecks=20_000),
                [SimpleNamespace(player_id=3, player_name="Player")],
                "ok",
            )

    monkeypatch.setattr(module, "SessionFactory", _Session)
    monkeypatch.setattr(module, "UserRepository", UserRepository)
    monkeypatch.setattr(module, "BetUseCases", BetUseCases)
    return captured


@pytest.mark.asyncio
async def test_telegram_draft_passes_canonical_actor_from_authenticated_boundary(monkeypatch):
    user = SimpleNamespace(row_id=41, name="Telegram User", is_approved=True)
    captured = _install_draft_fakes(monkeypatch, tg_bets, user=user)
    monkeypatch.setattr(tg_bets, "_ensure_approved_telegram_user", AsyncMock(return_value=True))
    monkeypatch.setattr(tg_bets, "betting_size_keyboard", lambda **kwargs: "keyboard")
    message = SimpleNamespace(
        from_user=SimpleNamespace(id=777),
        answer=AsyncMock(),
    )

    await tg_bets.start_make_bet(message, _State())

    assert captured["telegram_id"] == 777
    assert captured["draft_kwargs"] == {
        "actor_user_id": 41,
        "tournament_type": "single",
    }


@pytest.mark.asyncio
async def test_vk_draft_ignores_forged_callback_actor_and_uses_authenticated_boundary(
    monkeypatch,
):
    user = SimpleNamespace(row_id=52, name="VK User", is_approved=True)
    captured = _install_draft_fakes(monkeypatch, vk_bets, user=user)
    monkeypatch.setattr(vk_bets, "_is_vk_user_approved", AsyncMock(return_value=True))
    monkeypatch.setattr(vk_bets, "send_vk_message_event_answer", AsyncMock())
    monkeypatch.setattr(vk_bets, "send_vk_message", AsyncMock())
    monkeypatch.setattr(vk_bets, "_delete_event_message_if_possible", AsyncMock())
    monkeypatch.setattr(vk_bets, "betting_size_keyboard", lambda **kwargs: "keyboard")
    vk_bets.vk_user_contexts.clear()
    vk_bets.vk_user_states.clear()

    await vk_bets.handle_bet_tournament_event(
        user_id=777,
        peer_id=777,
        event_id="event",
        conversation_message_id=1,
        callback_payload={"actor_user_id": 999_999},
        action="bet_tournament_regular",
    )

    assert captured["vk_id"] == 777
    assert captured["draft_kwargs"] == {
        "actor_user_id": 52,
        "tournament_type": "single",
    }


@pytest.mark.asyncio
async def test_vk_text_draft_passes_canonical_actor_from_authenticated_boundary(monkeypatch):
    user = SimpleNamespace(row_id=52, name="VK User", is_approved=True)
    captured = _install_draft_fakes(monkeypatch, vk_bets, user=user)
    monkeypatch.setattr(vk_bets, "send_vk_message", AsyncMock())
    monkeypatch.setattr(vk_bets, "betting_size_keyboard", lambda **kwargs: "keyboard")
    vk_bets.vk_user_contexts.clear()
    vk_bets.vk_user_states.clear()

    await vk_bets.handle_make_bet_text(
        user_id=777,
        text=Buttons.betting.MAKE_BET.value,
        raw_message={},
    )

    assert captured["vk_id"] == 777
    assert captured["draft_kwargs"] == {
        "actor_user_id": 52,
        "tournament_type": "single",
    }
