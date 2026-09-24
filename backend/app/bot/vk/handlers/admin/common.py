import logging
from datetime import date

from app.application.exceptions import (
    UserAlreadyApprovedError,
    UserLinkConflictError,
    UserNameRequiredError,
    UserNotFoundError,
)
from app.application.use_cases.user.approve_user import ApproveUserUseCase
from app.application.use_cases.user.correct_user import CorrectUserUseCase
from app.application.use_cases.user.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.user.reject_user import RejectUserUseCase
from app.bot.shared.guards import is_vk_admin
from app.bot.shared.texts.inline.vk.admin import common as InlineText
from app.bot.shared.texts.texts import Text
from app.bot.telegram.notifications import notify_user_about_approval
from app.bot.vk.api import (
    delete_vk_message,
    send_vk_message,
)
from app.bot.vk.keyboards import (
    main_keyboard,
)
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory


VK_BUYIN_NOTIFY_CASHIER_ONLY: set[tuple[int, int]] = set()
VK_MANUAL_RECEIPT_SELECTIONS: dict[tuple[int, int], set[int]] = {}
logger = logging.getLogger(__name__)


HANDLER_UNMATCHED = object()


def _shift_month(value: date, delta: int) -> date:
    total = value.year * 12 + (value.month - 1) + delta
    year = total // 12
    month = total % 12 + 1
    return date(year, month, 1)


def _parse_month_key(value: str) -> date:
    year_s, month_s = value.split("-")
    return date(int(year_s), int(month_s), 1)




































async def _clear_event_inline_keyboard_if_possible(
    *, peer_id: int | None, conversation_message_id: int | None
) -> None:
    if peer_id is None or conversation_message_id is None:
        return
    try:
        await delete_vk_message(
            peer_id=peer_id,
            conversation_message_id=conversation_message_id,
        )
    except Exception:
        return


async def _ensure_vk_admin_message(*, session, user_id: int) -> bool:
    return await is_vk_admin(session=session, vk_id=user_id)


async def _process_vk_approve(*, admin_user_id: int, row_id: int) -> str:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await is_vk_admin(session=session, vk_id=admin_user_id):
            return Text.admin.NO_RIGHTS.value

        use_case = ApproveUserUseCase(repository)
        try:
            approved_user = await use_case.execute(row_id=row_id)
        except UserNotFoundError:
            return Text.admin.REQUEST_NOT_FOUND.value

    if approved_user.vk_id is not None:
        await send_vk_message(
            user_id=approved_user.vk_id,
            message=Text.user.REGISTRATION_APPROVED.value,
            keyboard=main_keyboard,
        )
    if approved_user.telegram_id is not None:
        await notify_user_about_approval(telegram_id=approved_user.telegram_id, approved=True)

    return (
        f'{Text.admin.APPROVE_ACTION.value}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_1}{approved_user.row_id}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_2}{approved_user.name}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_3}{approved_user.telegram_id}{InlineText.PROCESS_VK_APPROVE_TEXT_01_PART_4}{approved_user.vk_id}'
    )


async def _process_vk_reject(*, admin_user_id: int, row_id: int) -> str:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await is_vk_admin(session=session, vk_id=admin_user_id):
            return Text.admin.NO_RIGHTS.value

        pending_user = await repository.get_by_row_id(row_id)
        if pending_user is None:
            return Text.admin.REQUEST_NOT_FOUND.value

        pending_vk_id = pending_user.vk_id
        pending_telegram_id = pending_user.telegram_id
        use_case = RejectUserUseCase(repository)
        try:
            await use_case.execute(row_id=row_id)
        except UserNotFoundError:
            return Text.admin.REQUEST_NOT_FOUND.value
        except UserAlreadyApprovedError:
            return Text.admin.REQUEST_ALREADY_APPROVED.value

    if pending_vk_id is not None:
        await send_vk_message(
            user_id=pending_vk_id,
            message=Text.user.REGISTRATION_NOT_APPROVED.value,
            keyboard=main_keyboard,
        )
    if pending_telegram_id is not None:
        await notify_user_about_approval(telegram_id=pending_telegram_id, approved=False)

    return f"{Text.admin.REJECT_ACTION.value}\n\nRow ID: {row_id}"


async def _process_vk_correct(
    *,
    admin_user_id: int,
    row_id: int,
    corrected_name: str,
) -> str:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await is_vk_admin(session=session, vk_id=admin_user_id):
            return Text.admin.NO_RIGHTS.value

        use_case = CorrectUserUseCase(repository)
        try:
            corrected_user = await use_case.execute(
                row_id=row_id,
                corrected_name=corrected_name,
            )
        except UserNotFoundError:
            return Text.admin.REQUEST_NOT_FOUND.value
        except UserNameRequiredError:
            return Text.admin.EMPTY_CORRECTED_NAME.value
        except UserAlreadyApprovedError:
            return Text.admin.REQUEST_ALREADY_APPROVED.value

    if corrected_user.vk_id is not None:
        await send_vk_message(
            user_id=corrected_user.vk_id,
            message=Text.user.REGISTRATION_APPROVED.value,
            keyboard=main_keyboard,
        )
    if corrected_user.telegram_id is not None:
        await notify_user_about_approval(telegram_id=corrected_user.telegram_id, approved=True)

    return (
        f'{Text.admin.CORRECT_ACTION.value}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_1}{corrected_user.row_id}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_2}{corrected_user.name}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_3}{corrected_user.telegram_id}{InlineText.PROCESS_VK_CORRECT_TEXT_01_PART_4}{corrected_user.vk_id}'
    )


async def _process_vk_link(
    *,
    admin_user_id: int,
    pending_row_id: int,
    existing_row_id: int,
) -> str:
    async with SessionFactory() as session:
        repository = UserRepository(session)
        if not await is_vk_admin(session=session, vk_id=admin_user_id):
            return Text.admin.NO_RIGHTS.value

        use_case = LinkPendingUserUseCase(repository)
        try:
            linked_user = await use_case.execute(
                pending_row_id=pending_row_id,
                existing_row_id=existing_row_id,
            )
        except UserNotFoundError:
            return Text.admin.USER_NOT_FOUND.value
        except UserLinkConflictError:
            return Text.admin.LINK_CONFLICT.value

    if linked_user.vk_id is not None:
        await send_vk_message(
            user_id=linked_user.vk_id,
            message=Text.user.REGISTRATION_APPROVED.value,
            keyboard=main_keyboard,
        )
    if linked_user.telegram_id is not None:
        await notify_user_about_approval(telegram_id=linked_user.telegram_id, approved=True)

    return (
        f'{Text.admin.LINK_SUCCESS.value}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_1}{linked_user.row_id}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_2}{linked_user.name}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_3}{linked_user.telegram_id}{InlineText.PROCESS_VK_LINK_TEXT_01_PART_4}{linked_user.vk_id}'
    )
