from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import (
    RegistrationNotAuthorizedError,
    UserAlreadyApprovedError,
    UserAlreadyRegisteredError,
    UserIdentityRequiredError,
    UserLinkConflictError,
    UserNameRequiredError,
    UserNotFoundError,
    UserRegistrationPendingError,
)
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


@dataclass(frozen=True)
class RegistrationUserResult:
    row_id: int
    name: str
    telegram_id: int | None
    vk_id: int | None
    notification_platform: str | None
    is_approved: bool


@dataclass(frozen=True)
class SubmitRegistrationResult:
    user: RegistrationUserResult
    telegram_admin_ids: tuple[int, ...]
    vk_admin_ids: tuple[int, ...]


def _result(user: User) -> RegistrationUserResult:
    return RegistrationUserResult(
        row_id=int(user.row_id),
        name=str(user.name),
        telegram_id=int(user.telegram_id) if user.telegram_id is not None else None,
        vk_id=int(user.vk_id) if user.vk_id is not None else None,
        notification_platform=user.notification_platform,
        is_approved=bool(user.is_approved),
    )


async def _require_admin(repository: UserRepository, actor_user_id: int | None) -> None:
    actor = await repository.get_by_row_id(actor_user_id or -1)
    if actor is None or not actor.is_approved or not actor.is_admin:
        raise RegistrationNotAuthorizedError


class SubmitRegistrationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self,
        *,
        name: str,
        telegram_id: int | None = None,
        vk_id: int | None = None,
        tel_number: str | None = None,
        bank_name: str | None = None,
        notification_platform: str | None = None,
    ) -> SubmitRegistrationResult:
        if telegram_id is None and vk_id is None:
            raise UserIdentityRequiredError
        normalized_name = " ".join(name.split()).title()
        if not normalized_name:
            raise UserNameRequiredError

        async with self.session.begin():
            repository = UserRepository(self.session)
            existing = None
            if telegram_id is not None:
                existing = await repository.get_by_telegram_id(telegram_id)
            if existing is None and vk_id is not None:
                existing = await repository.get_by_vk_id(vk_id)
            if existing is not None:
                if existing.is_approved:
                    raise UserAlreadyRegisteredError(int(existing.row_id))
                raise UserRegistrationPendingError(int(existing.row_id))

            user = await repository.add_without_commit(
                name=normalized_name,
                telegram_id=telegram_id,
                vk_id=vk_id,
                tel_number=tel_number,
                bank_name=bank_name,
                notification_platform=notification_platform,
            )
            telegram_admin_ids = tuple(await repository.list_admin_tg_ids())
            vk_admin_ids = tuple(await repository.list_admin_vk_ids())
            result = SubmitRegistrationResult(
                user=_result(user),
                telegram_admin_ids=telegram_admin_ids,
                vk_admin_ids=vk_admin_ids,
            )
        return result


class ApproveRegistrationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, actor_user_id: int | None, row_id: int) -> RegistrationUserResult:
        async with self.session.begin():
            repository = UserRepository(self.session)
            await _require_admin(repository, actor_user_id)
            user = await repository.get_by_row_id(row_id)
            if user is None:
                raise UserNotFoundError(row_id)
            await repository.approve_without_commit(user)
            result = _result(user)
        return result


class RejectRegistrationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(self, *, actor_user_id: int | None, row_id: int) -> RegistrationUserResult:
        async with self.session.begin():
            repository = UserRepository(self.session)
            await _require_admin(repository, actor_user_id)
            user = await repository.get_by_row_id(row_id)
            if user is None:
                raise UserNotFoundError(row_id)
            if user.is_approved:
                raise UserAlreadyApprovedError(row_id)
            result = _result(user)
            await repository.delete_without_commit(user)
        return result


class CorrectRegistrationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self, *, actor_user_id: int | None, row_id: int, corrected_name: str
    ) -> RegistrationUserResult:
        normalized_name = " ".join(corrected_name.split())
        if not normalized_name:
            raise UserNameRequiredError
        async with self.session.begin():
            repository = UserRepository(self.session)
            await _require_admin(repository, actor_user_id)
            user = await repository.get_by_row_id(row_id)
            if user is None:
                raise UserNotFoundError(row_id)
            if user.is_approved:
                raise UserAlreadyApprovedError(row_id)
            await repository.correct_name_and_approve_without_commit(
                user, corrected_name=normalized_name
            )
            result = _result(user)
        return result


class LinkRegistrationUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def execute(
        self, *, actor_user_id: int | None, pending_row_id: int, existing_row_id: int
    ) -> RegistrationUserResult:
        async with self.session.begin():
            repository = UserRepository(self.session)
            await _require_admin(repository, actor_user_id)
            pending = await repository.get_by_row_id(pending_row_id)
            if pending is None:
                raise UserNotFoundError(pending_row_id)
            existing = await repository.get_by_row_id(existing_row_id)
            if existing is None:
                raise UserNotFoundError(existing_row_id)
            if pending.telegram_id is not None and existing.telegram_id is not None:
                raise UserLinkConflictError("telegram_id")
            if pending.vk_id is not None and existing.vk_id is not None:
                raise UserLinkConflictError("vk_id")
            await repository.link_pending_user_without_commit(existing, pending)
            result = _result(existing)
        return result
