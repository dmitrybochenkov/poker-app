import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.exceptions import (
    RegistrationNotAuthorizedError,
    UserAlreadyApprovedError,
    UserLinkConflictError,
    UserNotFoundError,
)
from app.application.use_cases.user.registration import (
    ApproveRegistrationUseCase,
    CorrectRegistrationUseCase,
    LinkRegistrationUseCase,
    RejectRegistrationUseCase,
    SubmitRegistrationUseCase,
)
from app.db.base import Base
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


@pytest.fixture
async def registration_sessions():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[User.__table__])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield sessions
    await engine.dispose()


async def _seed(sessions, **values) -> int:
    async with sessions() as session, session.begin():
        user = User(**values)
        session.add(user)
        await session.flush()
        return int(user.row_id)


@pytest.mark.asyncio
async def test_submit_registration_commits_pending_user_and_returns_admin_recipients(
    registration_sessions,
):
    await _seed(
        registration_sessions,
        name="TG Admin",
        telegram_id=11,
        notification_platform="tg",
        is_admin=True,
        is_approved=True,
    )
    await _seed(
        registration_sessions,
        name="VK Admin",
        vk_id=22,
        notification_platform="vk",
        is_admin=True,
        is_approved=True,
    )

    async with registration_sessions() as session:
        result = await SubmitRegistrationUseCase(session).execute(
            name="  new   player ", telegram_id=33
        )

    assert result.user.name == "New Player"
    assert result.user.notification_platform == "tg"
    assert result.telegram_admin_ids == (11,)
    assert result.vk_admin_ids == (22,)
    async with registration_sessions() as session:
        stored = await UserRepository(session).get_by_row_id(result.user.row_id)
        assert stored is not None
        assert stored.is_approved is False


@pytest.mark.asyncio
async def test_admin_operations_require_canonical_approved_admin_without_mutation(
    registration_sessions,
):
    pending_id = await _seed(
        registration_sessions, name="Pending", telegram_id=40, is_approved=False
    )
    non_admin_id = await _seed(
        registration_sessions, name="Player", telegram_id=41, is_approved=True
    )

    async with registration_sessions() as session:
        with pytest.raises(RegistrationNotAuthorizedError):
            await ApproveRegistrationUseCase(session).execute(
                actor_user_id=non_admin_id, row_id=pending_id
            )

    async with registration_sessions() as session:
        pending = await session.get(User, pending_id)
        assert pending is not None
        assert pending.is_approved is False


@pytest.mark.asyncio
async def test_approve_correct_and_reject_preserve_legacy_outcomes(registration_sessions):
    admin_id = await _seed(
        registration_sessions,
        name="Admin",
        telegram_id=50,
        is_admin=True,
        is_approved=True,
    )
    approve_id = await _seed(registration_sessions, name="Approve", vk_id=51)
    correct_id = await _seed(registration_sessions, name="Correct", vk_id=52)
    reject_id = await _seed(registration_sessions, name="Reject", vk_id=53)

    async with registration_sessions() as session:
        approved = await ApproveRegistrationUseCase(session).execute(
            actor_user_id=admin_id, row_id=approve_id
        )
    assert approved.is_approved is True
    async with registration_sessions() as session:
        repeated = await ApproveRegistrationUseCase(session).execute(
            actor_user_id=admin_id, row_id=approve_id
        )
    assert repeated.is_approved is True

    async with registration_sessions() as session:
        corrected = await CorrectRegistrationUseCase(session).execute(
            actor_user_id=admin_id,
            row_id=correct_id,
            corrected_name="  Corrected   Name ",
        )
    assert (corrected.name, corrected.is_approved) == ("Corrected Name", True)
    async with registration_sessions() as session:
        with pytest.raises(UserAlreadyApprovedError):
            await CorrectRegistrationUseCase(session).execute(
                actor_user_id=admin_id, row_id=correct_id, corrected_name="Again"
            )

    async with registration_sessions() as session:
        rejected = await RejectRegistrationUseCase(session).execute(
            actor_user_id=admin_id, row_id=reject_id
        )
    assert rejected.row_id == reject_id
    async with registration_sessions() as session:
        assert await session.get(User, reject_id) is None
    async with registration_sessions() as session:
        with pytest.raises(UserNotFoundError):
            await RejectRegistrationUseCase(session).execute(
                actor_user_id=admin_id, row_id=reject_id
            )


@pytest.mark.asyncio
async def test_link_keeps_existing_canonical_user_and_rejects_identity_conflict(
    registration_sessions,
):
    admin_id = await _seed(
        registration_sessions,
        name="Admin",
        telegram_id=60,
        is_admin=True,
        is_approved=True,
    )
    existing_id = await _seed(
        registration_sessions,
        name="Canonical",
        vk_id=61,
        notification_platform="vk",
        is_approved=True,
    )
    pending_id = await _seed(
        registration_sessions,
        name="Alias",
        telegram_id=62,
        notification_platform="tg",
    )

    async with registration_sessions() as session:
        linked = await LinkRegistrationUseCase(session).execute(
            actor_user_id=admin_id,
            pending_row_id=pending_id,
            existing_row_id=existing_id,
        )
    assert linked.row_id == existing_id
    assert (linked.name, linked.telegram_id, linked.vk_id) == ("Canonical", 62, 61)
    assert linked.notification_platform == "vk"
    async with registration_sessions() as session:
        assert await session.get(User, pending_id) is None
        assert len((await session.execute(select(User))).scalars().all()) == 2

    conflict_pending_id = await _seed(registration_sessions, name="Conflict", telegram_id=63)
    async with registration_sessions() as session:
        with pytest.raises(UserLinkConflictError):
            await LinkRegistrationUseCase(session).execute(
                actor_user_id=admin_id,
                pending_row_id=conflict_pending_id,
                existing_row_id=existing_id,
            )
    async with registration_sessions() as session:
        assert await session.get(User, conflict_pending_id) is not None
