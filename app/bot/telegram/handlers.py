from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.bot.telegram.keyboards import main_keyboard
from app.bot.telegram.states import RegistrationState
from app.db.repositories.user_repository import UserRepository
from app.db.session import SessionFactory

router = Router()


@router.message(CommandStart())
async def start_command(message: Message, state: FSMContext) -> None:
  await state.clear()
  await message.answer(
    "Привет! Я бот покерного приложения. "
    "Нажми «Регистрация», чтобы отправить заявку администратору.",
    reply_markup=main_keyboard,
  )


@router.message(F.text == "Регистрация")
async def start_registration(message: Message, state: FSMContext) -> None:
  await state.set_state(RegistrationState.waiting_for_name)
  await message.answer("Отправь имя и фамилию одним сообщением. Например: Иван Иванов")


@router.message(RegistrationState.waiting_for_name)
async def finish_registration(message: Message, state: FSMContext) -> None:
  if message.from_user is None or not message.text:
    await message.answer("Не удалось прочитать данные. Попробуй ещё раз.")
    return

  name = " ".join(message.text.split())
  if len(name.split()) < 2:
    await message.answer("Нужно указать имя и фамилию одним сообщением.")
    return

  async with SessionFactory() as session:
    repository = UserRepository(session)
    use_case = RequestRegistrationUseCase(repository)

    try:
      await use_case.execute(
        name=name,
        telegram_id=message.from_user.id,
      )
    except UserIdentityRequiredError:
      await message.answer("Не удалось определить Telegram ID.")
      return
    except UserAlreadyRegisteredError:
      await message.answer("Ты уже зарегистрирован.", reply_markup=main_keyboard)
      await state.clear()
      return
    except UserRegistrationPendingError:
      await message.answer(
        "Твоя заявка уже ожидает подтверждения администратора.",
        reply_markup=main_keyboard,
      )
      await state.clear()
      return

  await state.clear()
  await message.answer(
    "Заявка отправлена администратору. Напишу, когда тебя подтвердят.",
    reply_markup=main_keyboard,
  )
