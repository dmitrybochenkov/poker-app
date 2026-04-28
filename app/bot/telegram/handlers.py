from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserLinkConflictError,
  UserNotFoundError,
  UserRegistrationPendingError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
from app.application.use_cases.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.make_admin import MakeAdminUseCase
from app.application.use_cases.reject_user import RejectUserUseCase
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.shared.buttons import Buttons
from app.bot.shared.texts import Text
from app.bot.telegram.keyboards import main_keyboard, registration_review_keyboard
from app.bot.telegram.notifications import (
  notify_admins_about_registration,
  notify_user_about_approval,
)
from app.bot.telegram.states import RegistrationState
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = Router()


def _format_link_candidates(users: list[User]) -> str:
  if not users:
    return Text.admin.LINK_CHOICES_EMPTY.value

  lines = [Text.admin.LINK_CHOICES_TITLE.value]
  for user in users[:20]:
    lines.append(f"{user.row_id} — {user.name}")

  if len(users) > 20:
    lines.append("...")

  return "\n".join(lines)


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
  await state.clear()
  await message.answer(
    Text.user.BOT_INFO.value,
    reply_markup=main_keyboard,
  )


@router.message(F.text == Buttons.new_user.REGISTRATION.value)
async def start_registration(message: Message, state: FSMContext) -> None:
  await state.set_state(RegistrationState.waiting_for_name)
  await message.answer(Text.user.REGISTRATION_NEW_USER.value)


@router.message(F.text == Buttons.new_user.ALREADY_REGISTERED_VK.value)
async def start_link_from_vk(message: Message, state: FSMContext) -> None:
  await state.set_state(RegistrationState.waiting_for_name)
  await message.answer(Text.user.REGISTRATION_LINK_VK.value)


@router.message(Command("make_admin"))
async def make_admin_command(message: Message) -> None:
  if message.from_user is None or message.text is None:
    await message.answer(Text.admin.MAKE_ADMIN_USAGE.value)
    return

  parts = message.text.split(maxsplit=1)
  if len(parts) != 2 or not parts[1].isdigit():
    await message.answer(Text.admin.MAKE_ADMIN_USAGE.value)
    return

  row_id = int(parts[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.admin.NO_RIGHTS.value)
      return

    use_case = MakeAdminUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await message.answer(Text.admin.USER_NOT_FOUND.value)
      return

  await message.answer(
    f"{Text.admin.MAKE_ADMIN_SUCCESS.value}\n\n"
    f"Row ID: {user.row_id}\n"
    f"Имя: {user.name}\n"
    f"Telegram ID: {user.telegram_id}",
  )


@router.message(RegistrationState.waiting_for_existing_row_id)
async def finish_link_pending_user(message: Message, state: FSMContext) -> None:
  if message.from_user is None or message.text is None:
    await message.answer(Text.admin.LINK_USAGE.value)
    return

  existing_row_id_text = message.text.strip()
  if not existing_row_id_text.isdigit():
    await message.answer(Text.admin.LINK_USAGE.value)
    return

  existing_row_id = int(existing_row_id_text)
  data = await state.get_data()
  pending_row_id = data.get("pending_row_id")
  review_chat_id = data.get("review_chat_id")
  review_message_id = data.get("review_message_id")

  if pending_row_id is None:
    await state.clear()
    await message.answer(Text.admin.REQUEST_NOT_FOUND.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await state.clear()
      await message.answer(Text.admin.NO_RIGHTS.value)
      return

    use_case = LinkPendingUserUseCase(repository)
    try:
      user = await use_case.execute(
        pending_row_id=pending_row_id,
        existing_row_id=existing_row_id,
      )
    except UserNotFoundError:
      await message.answer(Text.admin.USER_NOT_FOUND.value)
      return
    except UserLinkConflictError:
      await message.answer(Text.admin.LINK_CONFLICT.value)
      return

  if review_chat_id is not None and review_message_id is not None:
    from app.bot.telegram.runtime import telegram_bot

    if telegram_bot is not None:
      await telegram_bot.edit_message_text(
        chat_id=review_chat_id,
        message_id=review_message_id,
        text=(
          f"{Text.admin.LINK_SUCCESS.value}\n\n"
          f"Pending row_id: {pending_row_id}\n"
          f"Linked to row_id: {user.row_id}\n"
          f"Имя: {user.name}\n"
          f"Telegram ID: {user.telegram_id}\n"
          f"VK ID: {user.vk_id}"
        ),
      )

  await state.clear()
  await message.answer(
    f"{Text.admin.LINK_SUCCESS.value}\n\n"
    f"Row ID: {user.row_id}\n"
    f"Имя: {user.name}\n"
    f"Telegram ID: {user.telegram_id}\n"
    f"VK ID: {user.vk_id}",
  )


@router.message(RegistrationState.waiting_for_name)
async def finish_registration(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer(Text.user.REGISTRATION_READ_ERROR.value)
    return

  name = " ".join(message.text.split())
  if len(name.split()) < 2:
    await message.answer(Text.user.REGISTRATION_INVALID_NAME.value)
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    use_case = RequestRegistrationUseCase(repository)

    try:
      user = await use_case.execute(
        name=name,
        telegram_id=message.from_user.id,
      )
    except UserIdentityRequiredError:
      await message.answer(Text.user.REGISTRATION_ID_ERROR.value)
      return
    except UserAlreadyRegisteredError:
      await message.answer(Text.user.REGISTRATION_EXIST.value, reply_markup=main_keyboard)
      await state.clear()
      return
    except UserRegistrationPendingError:
      await message.answer(
        Text.user.REGISTRATION_PENDING.value,
        reply_markup=main_keyboard,
      )
      await state.clear()
      return

    admin_chat_ids = await repository.list_telegram_admin_ids()

  await notify_admins_about_registration(
    row_id=user.row_id,
    name=name,
    telegram_id=message.from_user.id,
    admin_chat_ids=admin_chat_ids,
    reply_markup=registration_review_keyboard(row_id=user.row_id),
  )
  await state.clear()
  await message.answer(
    Text.user.REGISTRATION_WAIT.value,
    reply_markup=main_keyboard,
  )


@router.callback_query(F.data.startswith("approve:"))
async def approve_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    use_case = ApproveUserUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return

  if user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} одобрена.\nИмя: {user.name}\nTelegram ID: {user.telegram_id}",
    )
  await callback.answer(Text.admin.APPROVE_ACTION.value)


@router.callback_query(F.data.startswith("reject:"))
async def reject_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    user = await repository.get_by_row_id(row_id)
    if user is None:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return

    user_telegram_id = user.telegram_id
    user_name = user.name

    use_case = RejectUserUseCase(repository)
    try:
      await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer(Text.admin.REQUEST_NOT_FOUND.value, show_alert=True)
      return
    except UserAlreadyApprovedError:
      await callback.answer(Text.admin.REQUEST_ALREADY_APPROVED.value, show_alert=True)
      return

  if user_telegram_id is not None:
    await notify_user_about_approval(telegram_id=user_telegram_id, approved=False)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} отклонена.\nИмя: {user_name}\nTelegram ID: {user_telegram_id}",
    )
  await callback.answer(Text.admin.REJECT_ACTION.value)


@router.callback_query(F.data.startswith("link:"))
async def link_registration_callback(callback: CallbackQuery, state: FSMContext) -> None:
  if callback.from_user is None:
    await callback.answer(Text.admin.IDENTIFY_USER_ERROR.value, show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer(Text.admin.NO_RIGHTS.value, show_alert=True)
      return

    approved_users = await repository.list_approved()

  await state.set_state(RegistrationState.waiting_for_existing_row_id)
  await state.update_data(
    pending_row_id=row_id,
    review_chat_id=callback.message.chat.id if callback.message is not None else None,
    review_message_id=callback.message.message_id if callback.message is not None else None,
  )
  await callback.answer(Text.admin.LINK_ACTION.value)
  if callback.message is not None:
    await callback.message.answer(Text.admin.LINK_PROMPT.value)
    await callback.message.answer(_format_link_candidates(approved_users))
