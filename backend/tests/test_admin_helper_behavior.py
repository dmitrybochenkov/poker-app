from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.bot.telegram import runtime as telegram_runtime
from app.bot.telegram.handlers.admin import buyins as tg_buyins
from app.bot.telegram.handlers.admin import players as tg_players
from app.bot.telegram.handlers.admin import poker as tg_poker
from app.bot.vk.handlers.admin import cashier as vk_cashier
from app.bot.vk.handlers.admin import chips as vk_chips
from app.bot.vk.handlers.admin import players as vk_players


@pytest.mark.parametrize("consumer", [tg_poker, vk_chips])
def test_admin_poker_result_formatting_is_stable(consumer):
    transfers = consumer._calculate_transfers(
        [
            {"name": "Loser", "money": -10_000},
            {"name": "Winner", "money": 10_000},
        ]
    )

    assert transfers == ["Loser ➡️ Winner 100 ₽"]
    assert consumer._winner_mark(is_streak=True) == "🛡️💍"
    assert (
        consumer._bet_mark(
            amount_kopecks=40_000,
            guessed_winner=True,
            guessed_loser=False,
        )
        == "🐔🍀"
    )


@pytest.mark.parametrize("consumer", [tg_buyins, vk_cashier])
def test_admin_user_chips_text_is_stable(consumer):
    assert consumer._build_user_chips_text(
        chips=250,
        money_kopecks=5_000,
        reaction="🙂",
    ) == (
        "Покер завершен. Посчитай свои фишки и отправь число мне.\n"
        "Введено: 250\n"
        "Итог: 50 ₽ 🙂"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("consumer", [tg_players, vk_players])
async def test_removed_player_notification_keeps_dual_platform_delivery(
    monkeypatch, consumer
):
    telegram_bot = SimpleNamespace(send_message=AsyncMock())
    monkeypatch.setattr(telegram_runtime, "telegram_bot", telegram_bot)
    notify = consumer._notify_user_removed_from_room
    send_vk_message = AsyncMock()
    monkeypatch.setitem(notify.__globals__, "send_vk_message", send_vk_message)
    user = SimpleNamespace(telegram_id=101, vk_id=202, is_admin=False)

    await notify(user=user)

    telegram_bot.send_message.assert_awaited_once()
    assert telegram_bot.send_message.await_args.kwargs["chat_id"] == 101
    send_vk_message.assert_awaited_once()
    assert send_vk_message.await_args.kwargs["user_id"] == 202
