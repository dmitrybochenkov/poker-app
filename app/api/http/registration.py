from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import (
  UserAlreadyRegisteredError,
  UserIdentityRequiredError,
  UserRegistrationPendingError,
)
from app.application.use_cases.list_pending_registrations import (
  ListPendingRegistrationsUseCase,
)
from app.application.use_cases.request_registration import RequestRegistrationUseCase
from app.db.dependencies import get_db_session
from app.db.repositories.user_repository import UserRepository
from app.schemas.registration import RegistrationRead, RegistrationRequest

router = APIRouter(prefix="/registration", tags=["registration"])


@router.post("/request", response_model=RegistrationRead, status_code=status.HTTP_201_CREATED)
async def request_registration(
  payload: RegistrationRequest,
  session: AsyncSession = Depends(get_db_session),
) -> RegistrationRead:
  repository = UserRepository(session)
  use_case = RequestRegistrationUseCase(repository)

  try:
    user = await use_case.execute(
      name=payload.name,
      telegram_id=payload.telegram_id,
      vk_id=payload.vk_id,
      tel_number=payload.tel_number,
      bank_name=payload.bank_name,
    )
  except UserIdentityRequiredError as error:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="telegram_id or vk_id is required",
    ) from error
  except UserAlreadyRegisteredError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User with row_id={error.row_id} is already registered",
    ) from error
  except UserRegistrationPendingError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User with row_id={error.row_id} is waiting for approval",
    ) from error

  return RegistrationRead.model_validate(user)


@router.get("/pending", response_model=list[RegistrationRead])
async def list_pending_registrations(
  session: AsyncSession = Depends(get_db_session),
) -> list[RegistrationRead]:
  repository = UserRepository(session)
  use_case = ListPendingRegistrationsUseCase(repository)

  users = await use_case.execute()
  return [RegistrationRead.model_validate(user) for user in users]
