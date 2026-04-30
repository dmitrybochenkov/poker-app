from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.exceptions import (
  UserAlreadyApprovedError,
  UserAlreadyExistsError,
  UserIdentityRequiredError,
  UserLinkConflictError,
  UserNameRequiredError,
  UserNotFoundError,
)
from app.application.use_cases.approve_user import ApproveUserUseCase
from app.application.use_cases.correct_user import CorrectUserUseCase
from app.application.use_cases.link_pending_user import LinkPendingUserUseCase
from app.application.use_cases.make_admin import MakeAdminUseCase
from app.application.use_cases.register_user import RegisterUserUseCase
from app.application.use_cases.reject_user import RejectUserUseCase
from app.db.dependencies import get_db_session
from app.db.repositories.user_repository import UserRepository
from app.schemas.user import UserCorrectionRequest, UserCreate, UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.post("", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(
  payload: UserCreate,
  session: AsyncSession = Depends(get_db_session),
) -> UserRead:
  repository = UserRepository(session)
  use_case = RegisterUserUseCase(repository)

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
  except UserNameRequiredError as error:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="name is required",
    ) from error
  except UserAlreadyExistsError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User with this {error.field} already exists",
    ) from error

  return UserRead.model_validate(user)


@router.get("", response_model=list[UserRead])
async def list_users(
  session: AsyncSession = Depends(get_db_session),
) -> list[UserRead]:
  repository = UserRepository(session)
  users = await repository.list_all()
  return [UserRead.model_validate(user) for user in users]


@router.post("/{row_id}/approve", response_model=UserRead)
async def approve_user(
  row_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> UserRead:
  repository = UserRepository(session)
  use_case = ApproveUserUseCase(repository)

  try:
    user = await use_case.execute(row_id=row_id)
  except UserNotFoundError as error:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with row_id={row_id} not found",
    ) from error

  return UserRead.model_validate(user)


@router.post("/{row_id}/correct", response_model=UserRead)
async def correct_user(
  row_id: int,
  payload: UserCorrectionRequest,
  session: AsyncSession = Depends(get_db_session),
) -> UserRead:
  repository = UserRepository(session)
  use_case = CorrectUserUseCase(repository)

  try:
    user = await use_case.execute(
      row_id=row_id,
      corrected_name=payload.name,
    )
  except UserNotFoundError as error:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with row_id={row_id} not found",
    ) from error
  except UserNameRequiredError as error:
    raise HTTPException(
      status_code=status.HTTP_400_BAD_REQUEST,
      detail="name is required",
    ) from error
  except UserAlreadyApprovedError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User with row_id={error.row_id} is already approved",
    ) from error

  return UserRead.model_validate(user)


@router.post("/{row_id}/make-admin", response_model=UserRead)
async def make_admin(
  row_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> UserRead:
  repository = UserRepository(session)
  use_case = MakeAdminUseCase(repository)

  try:
    user = await use_case.execute(row_id=row_id)
  except UserNotFoundError:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with row_id={row_id} not found",
    )

  return UserRead.model_validate(user)


@router.post("/{row_id}/link/{existing_row_id}", response_model=UserRead)
async def link_pending_user(
  row_id: int,
  existing_row_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> UserRead:
  repository = UserRepository(session)
  use_case = LinkPendingUserUseCase(repository)

  try:
    user = await use_case.execute(
      pending_row_id=row_id,
      existing_row_id=existing_row_id,
    )
  except UserNotFoundError as error:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with row_id={error.row_id} not found",
    ) from error
  except UserLinkConflictError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User already has {error.field}",
    ) from error

  return UserRead.model_validate(user)


@router.post("/{row_id}/reject", status_code=status.HTTP_204_NO_CONTENT)
async def reject_user(
  row_id: int,
  session: AsyncSession = Depends(get_db_session),
) -> None:
  repository = UserRepository(session)
  use_case = RejectUserUseCase(repository)

  try:
    await use_case.execute(row_id=row_id)
  except UserNotFoundError as error:
    raise HTTPException(
      status_code=status.HTTP_404_NOT_FOUND,
      detail=f"User with row_id={row_id} not found",
    ) from error
  except UserAlreadyApprovedError as error:
    raise HTTPException(
      status_code=status.HTTP_409_CONFLICT,
      detail=f"User with row_id={row_id} is already approved",
    ) from error
