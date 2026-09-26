from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.exceptions import (
    UserAlreadyApprovedError,
    UserAlreadyRegisteredError,
    UserLinkConflictError,
    UserNotFoundError,
    UserRegistrationPendingError,
)
from app.application.use_cases.user.approve_user import ApproveUserUseCase
from app.application.use_cases.user.correct_user import CorrectUserUseCase
from app.application.use_cases.user.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.user.reject_user import RejectUserUseCase
from app.application.use_cases.user.request_registration import RequestRegistrationUseCase
from app.bot.shared.texts.texts import Text
from app.bot.telegram.handlers.admin import registrations as tg_admin
from app.bot.telegram.handlers.user import common as tg_user_common
from app.bot.vk.handlers.admin import common as vk_admin_common
from app.bot.vk.handlers.user import common as vk_user_common
from app.bot.vk.state import vk_user_contexts, vk_user_states
from app.db.base import Base
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


@pytest.fixture
async def registration_db():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[User.__table__])
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    yield sessions
    await engine.dispose()


@pytest.mark.asyncio
async def test_current_submit_registration_identity_and_duplicate_lifecycle(registration_db):
    async with registration_db() as session:
        tg_user = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="  иван   иванов ", telegram_id=101
        )
        assert (
            tg_user.name,
            tg_user.telegram_id,
            tg_user.vk_id,
            tg_user.notification_platform,
            tg_user.is_approved,
        ) == ("Иван Иванов", 101, None, "tg", False)
        canonical_id = int(tg_user.row_id)

        with pytest.raises(UserRegistrationPendingError) as pending:
            await RequestRegistrationUseCase(UserRepository(session)).execute(
                name="Other", telegram_id=101
            )
        assert pending.value.row_id == canonical_id

        await ApproveUserUseCase(UserRepository(session)).execute(row_id=canonical_id)
        with pytest.raises(UserAlreadyRegisteredError) as registered:
            await RequestRegistrationUseCase(UserRepository(session)).execute(
                name="Other", telegram_id=101
            )
        assert registered.value.row_id == canonical_id

    async with registration_db() as session:
        vk_user = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="VK User", vk_id=202
        )
        assert (vk_user.telegram_id, vk_user.vk_id, vk_user.notification_platform) == (
            None,
            202,
            "vk",
        )


@pytest.mark.asyncio
async def test_current_approve_and_correct_repeated_action_semantics(registration_db):
    async with registration_db() as session:
        first = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="First", telegram_id=1
        )
        use_case = ApproveUserUseCase(UserRepository(session))
        await use_case.execute(row_id=int(first.row_id))
        repeated = await use_case.execute(row_id=int(first.row_id))
        assert repeated.is_approved is True

        second = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="Second", vk_id=2
        )
        corrected = await CorrectUserUseCase(UserRepository(session)).execute(
            row_id=int(second.row_id), corrected_name="  Corrected   name "
        )
        assert (corrected.name, corrected.is_approved) == ("Corrected name", True)
        with pytest.raises(UserAlreadyApprovedError):
            await CorrectUserUseCase(UserRepository(session)).execute(
                row_id=int(second.row_id), corrected_name="Again"
            )


@pytest.mark.asyncio
async def test_current_reject_and_repeated_reject_semantics(registration_db):
    async with registration_db() as session:
        pending = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="Pending", telegram_id=3
        )
        row_id = int(pending.row_id)
        await RejectUserUseCase(UserRepository(session)).execute(row_id=row_id)
        assert await session.get(User, row_id) is None
        with pytest.raises(UserNotFoundError):
            await RejectUserUseCase(UserRepository(session)).execute(row_id=row_id)

        approved = await RequestRegistrationUseCase(UserRepository(session)).execute(
            name="Approved", vk_id=4
        )
        await ApproveUserUseCase(UserRepository(session)).execute(row_id=int(approved.row_id))
        with pytest.raises(UserAlreadyApprovedError):
            await RejectUserUseCase(UserRepository(session)).execute(row_id=int(approved.row_id))


@pytest.mark.asyncio
async def test_current_link_preserves_canonical_row_and_platform_identities(registration_db):
    async with registration_db() as session:
        repository = UserRepository(session)
        existing = await repository.create(name="Canonical", vk_id=20, is_approved=True)
        pending = await RequestRegistrationUseCase(repository).execute(
            name="Pending alias", telegram_id=10, notification_platform="tg"
        )
        existing_id = int(existing.row_id)
        pending_id = int(pending.row_id)

        linked = await LinkPendingUserUseCase(repository).execute(
            pending_row_id=pending_id, existing_row_id=existing_id
        )

        assert int(linked.row_id) == existing_id
        assert (linked.telegram_id, linked.vk_id, linked.name, linked.is_approved) == (
            10,
            20,
            "Canonical",
            True,
        )
        assert linked.notification_platform == "vk"
        assert await session.get(User, pending_id) is None
        assert len((await session.execute(select(User))).scalars().all()) == 1


@pytest.mark.asyncio
async def test_current_link_missing_and_conflict_outcomes(registration_db):
    async with registration_db() as session:
        repository = UserRepository(session)
        with pytest.raises(UserNotFoundError):
            await LinkPendingUserUseCase(repository).execute(
                pending_row_id=999, existing_row_id=998
            )

        existing = await repository.create(name="Existing", telegram_id=1, is_approved=True)
        pending = await repository.create(name="Pending", telegram_id=2)
        with pytest.raises(UserLinkConflictError) as conflict:
            await LinkPendingUserUseCase(repository).execute(
                pending_row_id=int(pending.row_id), existing_row_id=int(existing.row_id)
            )
        assert conflict.value.field == "telegram_id"


class _Session:
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_current_telegram_admin_authorization_stops_approval(monkeypatch):
    callback = SimpleNamespace(
        from_user=SimpleNamespace(id=77), data="approve:42", answer=AsyncMock()
    )
    use_case = Mock()
    monkeypatch.setattr(tg_admin, "SessionFactory", _Session)
    monkeypatch.setattr(tg_admin, "UserRepository", Mock())
    monkeypatch.setattr(tg_admin, "_clear_inline_keyboard", AsyncMock())
    monkeypatch.setattr(tg_admin, "_ensure_tg_admin_callback", AsyncMock(return_value=False))
    monkeypatch.setattr(tg_admin, "ApproveRegistrationUseCase", use_case)

    await tg_admin.approve_registration_callback(callback)

    use_case.assert_not_called()
    callback.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_current_vk_admin_authorization_stops_approval(monkeypatch):
    monkeypatch.setattr(vk_admin_common, "SessionFactory", _Session)
    monkeypatch.setattr(vk_admin_common, "is_vk_admin", AsyncMock(return_value=False))
    use_case = Mock()
    monkeypatch.setattr(vk_admin_common, "ApproveRegistrationUseCase", use_case)

    result = await vk_admin_common._process_vk_approve(admin_user_id=77, row_id=42)

    assert result == Text.admin.NO_RIGHTS.value
    use_case.assert_not_called()


@pytest.mark.asyncio
async def test_current_telegram_submit_notifies_both_admin_platforms_after_creation(monkeypatch):
    user = SimpleNamespace(row_id=42)
    result = SimpleNamespace(
        user=user,
        telegram_admin_ids=(1,),
        vk_admin_ids=(2,),
    )
    execute = AsyncMock(return_value=result)
    monkeypatch.setattr(tg_user_common, "SessionFactory", _Session)
    monkeypatch.setattr(
        tg_user_common,
        "SubmitRegistrationUseCase",
        lambda session: SimpleNamespace(execute=execute),
    )
    tg_notify = AsyncMock()
    vk_notify = AsyncMock()
    monkeypatch.setattr(tg_user_common, "notify_admins_about_registration", tg_notify)
    monkeypatch.setattr(tg_user_common, "notify_vk_admins_about_registration", vk_notify)
    message = SimpleNamespace(from_user=SimpleNamespace(id=100), answer=AsyncMock())
    state = SimpleNamespace(clear=AsyncMock())

    await tg_user_common._submit_registration_request(
        message=message,
        state=state,
        name="User",
        success_text="wait",
    )

    execute.assert_awaited_once_with(
        name="User",
        telegram_id=100,
        bank_name=None,
        tel_number=None,
        notification_platform=None,
    )
    tg_notify.assert_awaited_once()
    vk_notify.assert_awaited_once()
    state.clear.assert_awaited_once()
    message.answer.assert_awaited_once_with("wait", reply_markup=tg_user_common.new_user_keyboard)


@pytest.mark.asyncio
async def test_current_vk_submit_clears_state_and_notifies_both_admin_platforms(monkeypatch):
    user_id = 200
    user = SimpleNamespace(row_id=43)
    result = SimpleNamespace(
        user=user,
        telegram_admin_ids=(1,),
        vk_admin_ids=(2,),
    )
    execute = AsyncMock(return_value=result)
    monkeypatch.setattr(vk_user_common, "SessionFactory", _Session)
    monkeypatch.setattr(
        vk_user_common,
        "SubmitRegistrationUseCase",
        lambda session: SimpleNamespace(execute=execute),
    )
    tg_notify = AsyncMock()
    vk_notify = AsyncMock()
    send = AsyncMock()
    monkeypatch.setattr(vk_user_common, "notify_tg_admins_about_registration", tg_notify)
    monkeypatch.setattr(vk_user_common, "notify_admins_about_registration", vk_notify)
    monkeypatch.setattr(vk_user_common, "send_vk_message", send)
    vk_user_states[user_id] = "state"
    vk_user_contexts[user_id] = {"data": "value"}

    await vk_user_common._submit_registration_request(
        user_id=user_id,
        name="User",
        success_message="wait",
    )

    assert user_id not in vk_user_states
    assert user_id not in vk_user_contexts
    tg_notify.assert_awaited_once()
    vk_notify.assert_awaited_once()
    send.assert_awaited_once_with(
        user_id=user_id,
        message="wait",
        keyboard=vk_user_common.new_user_keyboard,
    )


@pytest.mark.asyncio
async def test_registration_stays_committed_when_post_commit_notification_fails(
    registration_db, monkeypatch
):
    monkeypatch.setattr(tg_user_common, "SessionFactory", registration_db)
    monkeypatch.setattr(
        tg_user_common,
        "notify_admins_about_registration",
        AsyncMock(side_effect=RuntimeError("delivery failed")),
    )
    monkeypatch.setattr(
        tg_user_common, "notify_vk_admins_about_registration", AsyncMock()
    )
    message = SimpleNamespace(from_user=SimpleNamespace(id=300), answer=AsyncMock())
    state = SimpleNamespace(clear=AsyncMock())

    with pytest.raises(RuntimeError, match="delivery failed"):
        await tg_user_common._submit_registration_request(
            message=message,
            state=state,
            name="Committed User",
            success_text="wait",
        )

    async with registration_db() as session:
        stored = await UserRepository(session).get_by_telegram_id(300)
    assert stored is not None
    assert stored.name == "Committed User"
    assert stored.is_approved is False
