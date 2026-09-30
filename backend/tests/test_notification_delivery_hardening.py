import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.telegram import notifications as tg_notifications
from app.bot.telegram import runtime as telegram_runtime
from app.bot.telegram.handlers.admin import buyins as tg_buyins
from app.bot.telegram.handlers.admin import player_notification_helpers as tg_player_notifications
from app.bot.telegram.handlers.admin import polls as tg_polls
from app.bot.vk import notifications as vk_notifications
from app.bot.vk.handlers.admin import player_notification_helpers as vk_player_notifications
from app.bot.vk.handlers.admin import polls as vk_polls
from app.db.base import Base
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.poll_config import PollConfig
from app.db.models.user import User


@pytest.fixture
async def notification_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(
            Base.metadata.create_all,
            tables=[
                User.__table__,
                BuyinData.__table__,
                PokerParam.__table__,
                Poker.__table__,
                PokerData.__table__,
                PollConfig.__table__,
            ],
        )
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield sessions
    await engine.dispose()


async def _seed_fanout_users(sessions):
    async with sessions() as session:
        cashier = User(
            name="Cashier", telegram_id=101, is_approved=True, is_admin=True,
            notification_platform="tg",
        )
        failing_admin = User(
            name="Failing admin", telegram_id=102, is_approved=True, is_admin=True,
            notification_platform="tg",
        )
        later_admin = User(
            name="Later admin", vk_id=203, is_approved=True, is_admin=True,
            notification_platform="vk",
        )
        player = User(
            name="Player", telegram_id=104, is_approved=True,
            notification_platform="tg",
        )
        session.add_all([cashier, failing_admin, later_admin, player])
        await session.flush()
        params = PokerParam(
            buyin_size_chips=200,
            buyin_size_kopecks=20_000,
            bb_size_chips=10,
            max_buyins=3,
        )
        session.add(params)
        await session.flush()
        poker = Poker(params_id=int(params.row_id), cashier_id=int(cashier.row_id))
        session.add(poker)
        await session.flush()
        for user in (cashier, failing_admin, later_admin, player):
            session.add(
                PokerData(
                    poker_id=int(poker.row_id),
                    date=poker.date,
                    player_id=int(user.row_id),
                    player_name=user.name,
                )
            )
        await session.commit()
        return cashier, failing_admin, later_admin, player, poker


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module", [tg_player_notifications, vk_player_notifications], ids=["tg", "vk"]
)
@pytest.mark.parametrize("failed_role", ["cashier", "admin"])
async def test_buyin_failure_does_not_stop_later_recipients(
    notification_sessions, monkeypatch, module, failed_role, caplog
):
    cashier, failing_admin, later_admin, player, poker = await _seed_fanout_users(
        notification_sessions
    )
    attempted = []
    failed_telegram_id = (
        int(cashier.telegram_id)
        if failed_role == "cashier"
        else int(failing_admin.telegram_id)
    )

    async def send_tg(*, chat_id, **kwargs):
        attempted.append(("tg", int(chat_id)))
        if int(chat_id) == failed_telegram_id:
            raise RuntimeError("blocked")

    async def send_vk(*, user_id, **kwargs):
        attempted.append(("vk", int(user_id)))

    monkeypatch.setattr(
        telegram_runtime, "telegram_bot", SimpleNamespace(send_message=send_tg)
    )
    monkeypatch.setitem(module._notify_about_buyin.__globals__, "send_vk_message", send_vk)
    caplog.set_level(logging.ERROR)

    async with notification_sessions() as session:
        await module._notify_about_buyin(
            session=session,
            poker=SimpleNamespace(
                row_id=int(poker.row_id),
                date=poker.date,
                cashier_id=int(cashier.row_id),
            ),
            updated_player=SimpleNamespace(
                player_id=int(player.row_id), player_name=player.name, buyins=1
            ),
            buyins_count=1,
        )

    assert ("vk", int(later_admin.vk_id)) in attempted
    assert ("tg", int(player.telegram_id)) in attempted
    assert "buyin" in caplog.text.lower()
    assert str(failed_telegram_id) in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "module", [tg_player_notifications, vk_player_notifications], ids=["tg", "vk"]
)
async def test_removed_player_delivery_and_admin_fanout_are_isolated(
    notification_sessions, monkeypatch, module, caplog
):
    _, failing_admin, later_admin, player, poker = await _seed_fanout_users(
        notification_sessions
    )
    attempted = []

    async def send_tg(*, chat_id, **kwargs):
        attempted.append(("tg", int(chat_id)))
        if int(chat_id) in {int(player.telegram_id), int(failing_admin.telegram_id)}:
            raise RuntimeError("blocked")

    async def send_vk(*, user_id, **kwargs):
        attempted.append(("vk", int(user_id)))

    monkeypatch.setattr(
        telegram_runtime, "telegram_bot", SimpleNamespace(send_message=send_tg)
    )
    monkeypatch.setitem(module._notify_user_removed_from_room.__globals__, "send_vk_message", send_vk)
    caplog.set_level(logging.ERROR)

    await module._notify_user_removed_from_room(
        user=SimpleNamespace(
            row_id=int(player.row_id), telegram_id=player.telegram_id,
            vk_id=904, is_admin=False,
        )
    )
    async with notification_sessions() as session:
        await module._notify_admins_about_removed_player(
            session=session,
            poker_date=poker.date,
            player_name=player.name,
            buyins=1,
        )

    assert ("vk", 904) in attempted
    assert ("vk", int(later_admin.vk_id)) in attempted
    assert "removed" in caplog.text.lower()


@pytest.mark.asyncio
async def test_buyin_actor_acknowledgement_survives_fanout_failure(
    notification_sessions, monkeypatch
):
    cashier, failing_admin, _, player, _ = await _seed_fanout_users(notification_sessions)

    async def send_tg(*, chat_id, **kwargs):
        if int(chat_id) == int(failing_admin.telegram_id):
            raise RuntimeError("blocked")

    monkeypatch.setattr(tg_buyins, "SessionFactory", notification_sessions)
    monkeypatch.setattr(
        telegram_runtime, "telegram_bot", SimpleNamespace(send_message=send_tg)
    )
    monkeypatch.setitem(
        tg_player_notifications._notify_about_buyin.__globals__,
        "send_vk_message",
        AsyncMock(),
    )
    callback = SimpleNamespace(
        id="callback-fanout-failure",
        data=f"pokerbuyincount:{int(player.row_id)}:1",
        from_user=SimpleNamespace(id=int(cashier.telegram_id)),
        message=None,
        answer=AsyncMock(),
    )

    await tg_buyins.buyin_count_callback(callback)

    callback.answer.assert_awaited_once_with(
        tg_buyins.Text.admin.POKER_BUYIN_SAVED.value
    )


@pytest.mark.asyncio
async def test_tg_registration_admin_failure_does_not_stop_later_admin(monkeypatch, caplog):
    attempted = []

    async def send(*, chat_id, **kwargs):
        attempted.append(chat_id)
        if chat_id == 2:
            raise RuntimeError("blocked")

    monkeypatch.setattr(telegram_runtime, "telegram_bot", SimpleNamespace(send_message=send))
    caplog.set_level(logging.ERROR)
    await tg_notifications.notify_admins_about_registration(
        name="User", telegram_id=10, requester_platform="tg", admin_chat_ids=[1, 2, 3]
    )
    assert attempted == [1, 2, 3]
    assert "registration" in caplog.text.lower() and "2" in caplog.text


@pytest.mark.asyncio
async def test_vk_registration_admin_failure_does_not_stop_later_admin(monkeypatch, caplog):
    attempted = []

    async def send(*, user_id, **kwargs):
        attempted.append(user_id)
        if user_id == 2:
            raise RuntimeError("blocked")

    monkeypatch.setattr(vk_notifications, "send_vk_message", send)
    caplog.set_level(logging.ERROR)
    await vk_notifications.notify_admins_about_registration(
        name="User", vk_id=10, requester_platform="vk", admin_ids=[1, 2, 3]
    )
    assert attempted == [1, 2, 3]
    assert "registration" in caplog.text.lower() and "2" in caplog.text


@pytest.mark.asyncio
@pytest.mark.parametrize("module", [tg_polls, vk_polls], ids=["tg", "vk"])
async def test_poll_failure_is_logged_and_later_recipient_is_attempted(
    notification_sessions, monkeypatch, module, caplog
):
    async with notification_sessions() as session:
        session.add_all(
            [
                User(name="Admin", telegram_id=1, vk_id=11, is_approved=True, is_admin=True),
                User(name="Failing", telegram_id=2, vk_id=12, is_approved=True),
                User(name="Later", telegram_id=3, vk_id=13, is_approved=True),
            ]
        )
        await session.commit()
    attempted = []

    async def send_tg(*, chat_id, **kwargs):
        attempted.append(("tg", int(chat_id)))
        if int(chat_id) == 2:
            raise RuntimeError("blocked")

    async def send_vk(*, user_id, **kwargs):
        attempted.append(("vk", int(user_id)))

    monkeypatch.setattr(module, "SessionFactory", notification_sessions)
    monkeypatch.setattr(
        telegram_runtime, "telegram_bot", SimpleNamespace(send_message=send_tg)
    )
    monkeypatch.setattr(module, "send_vk_message", send_vk)
    caplog.set_level(logging.ERROR)

    if module is tg_polls:
        callback = SimpleNamespace(
            from_user=SimpleNamespace(id=1), data="polladmin_month:2026-10",
            message=None, answer=AsyncMock(),
        )
        await module.create_poll_set_month(callback)
    else:
        await module.handle_polladmin_month_event(
            admin_user_id=11,
            peer_id=11,
            event_id="event",
            conversation_message_id=1,
            callback_payload={"month": "2026-10"},
            action="polladmin_month",
            handle_admin_text_commands=AsyncMock(),
        )

    assert ("tg", 3) in attempted
    assert "poll invitation" in caplog.text.lower()
    assert "2" in caplog.text
