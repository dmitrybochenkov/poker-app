from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserNotFoundError,
  UserRegistrationPendingError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
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
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = Router()


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


@router.message(Command("make_admin"))
async def make_admin_command(message: Message) -> None:
  if message.from_user is None or message.text is None:
    await message.answer(Text.user.ADMIN_MAKE_ADMIN_USAGE.value)
    return

  parts = message.text.split(maxsplit=1)
  if len(parts) != 2 or not parts[1].isdigit():
    await message.answer(Text.user.ADMIN_MAKE_ADMIN_USAGE.value)
    return

  row_id = int(parts[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if message.from_user.id not in admin_ids:
      await message.answer(Text.user.ADMIN_NO_RIGHTS.value)
      return

    use_case = MakeAdminUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await message.answer(Text.user.ADMIN_USER_NOT_FOUND.value)
      return

  await message.answer(
    f"{Text.user.ADMIN_MAKE_ADMIN_SUCCESS.value}\n\n"
    f"Row ID: {user.row_id}\n"
    f"Имя: {user.name}\n"
    f"Telegram ID: {user.telegram_id}",
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
    await callback.answer("Не удалось определить пользователя.", show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer("Недостаточно прав.", show_alert=True)
      return

    use_case = ApproveUserUseCase(repository)
    try:
      user = await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer("Заявка не найдена.", show_alert=True)
      return

  if user.telegram_id is not None:
    await notify_user_about_approval(telegram_id=user.telegram_id, approved=True)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} одобрена.\nИмя: {user.name}\nTelegram ID: {user.telegram_id}",
    )
  await callback.answer("Заявка одобрена.")


@router.callback_query(F.data.startswith("reject:"))
async def reject_registration_callback(callback: CallbackQuery) -> None:
  if callback.from_user is None:
    await callback.answer("Не удалось определить пользователя.", show_alert=True)
    return

  row_id = int(callback.data.split(":", 1)[1])

  async with SessionFactory() as session:
    repository = UserRepository(session)
    admin_ids = await repository.list_telegram_admin_ids()
    if callback.from_user.id not in admin_ids:
      await callback.answer("Недостаточно прав.", show_alert=True)
      return

    user = await repository.get_by_row_id(row_id)
    if user is None:
      await callback.answer("Заявка не найдена.", show_alert=True)
      return

    user_telegram_id = user.telegram_id
    user_name = user.name

    use_case = RejectUserUseCase(repository)
    try:
      await use_case.execute(row_id=row_id)
    except UserNotFoundError:
      await callback.answer("Заявка не найдена.", show_alert=True)
      return
    except UserAlreadyApprovedError:
      await callback.answer("Одобренную заявку нельзя отклонить.", show_alert=True)
      return

  if user_telegram_id is not None:
    await notify_user_about_approval(telegram_id=user_telegram_id, approved=False)

  if callback.message is not None:
    await callback.message.edit_text(
      f"Заявка #{row_id} отклонена.\nИмя: {user_name}\nTelegram ID: {user_telegram_id}",
    )
  await callback.answer("Заявка отклонена.")
