import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.use_cases.poker.start_poker import (
  PokerAlreadyStartedError,
  PokerParamsNotFoundError,
  StartPokerNotAuthorizedError,
  StartPokerUseCase,
)
from app.db.base import Base
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.poker_param import PokerParam
from app.db.models.user import User
from app.services.start_poker_flow import StartPokerFlow


async def _session_factory(url: str = "sqlite+aiosqlite:///:memory:"):
  engine = create_async_engine(url)
  async with engine.begin() as connection:
    await connection.run_sync(
      Base.metadata.create_all,
      tables=[User.__table__, PokerParam.__table__, Poker.__table__, PokerData.__table__],
    )
  return engine, async_sessionmaker(engine, expire_on_commit=False)


async def _seed(session_factory, *, actor_approved=True, actor_admin=True):
  async with session_factory() as session:
    actor = User(
      name="Admin",
      telegram_id=1,
      notification_platform="tg",
      is_approved=actor_approved,
      is_admin=actor_admin,
    )
    dual = User(
      name="Dual",
      telegram_id=2,
      vk_id=3,
      notification_platform="tg",
      is_approved=True,
    )
    pending = User(name="Pending", telegram_id=4, is_approved=False)
    params = PokerParam(
      buyin_size_chips=200,
      buyin_size_kopecks=20_000,
      bb_size_chips=10,
      max_buyins=3,
    )
    session.add_all([actor, dual, pending, params])
    await session.commit()
    return int(actor.row_id), int(params.row_id), (int(actor.row_id), int(dual.row_id))


@pytest.mark.asyncio
async def test_start_poker_commits_game_starter_and_all_approved_recipients() -> None:
  engine, session_factory = await _session_factory()
  actor_id, params_id, expected_recipients = await _seed(session_factory)

  async with session_factory() as session:
    result = await StartPokerUseCase(session).execute(
      actor_user_id=actor_id,
      params_id=params_id,
    )

  assert result.recipient_user_ids == expected_recipients
  async with session_factory() as session:
    poker = await session.get(Poker, result.poker_id)
    starter = await session.scalar(
      select(PokerData).where(PokerData.player_id == actor_id)
    )
    assert poker is not None and poker.is_going is True
    assert starter is not None
    assert starter.date == poker.date
    assert starter.player_name == "Admin"
  await engine.dispose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
  ("seed_options", "actor_override", "params_override", "error_type"),
  [
    ({"actor_admin": False}, None, None, StartPokerNotAuthorizedError),
    ({"actor_approved": False}, None, None, StartPokerNotAuthorizedError),
    ({}, 999_999, None, StartPokerNotAuthorizedError),
    ({}, None, 999_999, PokerParamsNotFoundError),
  ],
)
async def test_start_poker_rejects_invalid_request_without_mutation(
  seed_options,
  actor_override,
  params_override,
  error_type,
) -> None:
  engine, session_factory = await _session_factory()
  actor_id, params_id, _ = await _seed(session_factory, **seed_options)

  async with session_factory() as session:
    with pytest.raises(error_type):
      await StartPokerUseCase(session).execute(
        actor_user_id=actor_override or actor_id,
        params_id=params_override or params_id,
      )

  async with session_factory() as session:
    assert await session.scalar(select(func.count()).select_from(Poker)) == 0
    assert await session.scalar(select(func.count()).select_from(PokerData)) == 0
  await engine.dispose()


@pytest.mark.asyncio
async def test_start_poker_repeated_execution_creates_only_one_active_game() -> None:
  engine, session_factory = await _session_factory()
  actor_id, params_id, _ = await _seed(session_factory)

  async with session_factory() as session:
    await StartPokerUseCase(session).execute(actor_user_id=actor_id, params_id=params_id)
  async with session_factory() as session:
    with pytest.raises(PokerAlreadyStartedError):
      await StartPokerUseCase(session).execute(actor_user_id=actor_id, params_id=params_id)

  async with session_factory() as session:
    assert await session.scalar(select(func.count()).select_from(Poker)) == 1
    assert await session.scalar(select(func.count()).select_from(PokerData)) == 1
  await engine.dispose()


@pytest.mark.asyncio
async def test_concurrent_start_poker_creates_one_active_game(tmp_path) -> None:
  engine, session_factory = await _session_factory(
    f"sqlite+aiosqlite:///{tmp_path / 'start-poker.db'}"
  )
  actor_id, params_id, _ = await _seed(session_factory)

  async def execute():
    async with session_factory() as session:
      return await StartPokerUseCase(session).execute(
        actor_user_id=actor_id,
        params_id=params_id,
      )

  results = await asyncio.gather(execute(), execute(), return_exceptions=True)

  assert sum(not isinstance(result, Exception) for result in results) == 1
  assert sum(isinstance(result, PokerAlreadyStartedError) for result in results) == 1
  async with session_factory() as session:
    assert await session.scalar(select(func.count()).select_from(Poker)) == 1
    assert await session.scalar(select(func.count()).select_from(PokerData)) == 1
  await engine.dispose()


@pytest.mark.asyncio
async def test_notification_failure_does_not_rollback_started_poker() -> None:
  engine, session_factory = await _session_factory()
  actor_id, params_id, _ = await _seed(session_factory)

  class FailingNotifier:
    async def notify(self, *, user_ids):
      raise RuntimeError("network unavailable")

  result = await StartPokerFlow(
    session_factory=session_factory,
    notifier=FailingNotifier(),
  ).execute(actor_user_id=actor_id, params_id=params_id)

  async with session_factory() as session:
    assert await session.get(Poker, result.poker_id) is not None
    assert await session.scalar(select(func.count()).select_from(PokerData)) == 1
  await engine.dispose()
