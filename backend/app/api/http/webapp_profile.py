from datetime import datetime
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from PIL import Image, ImageOps
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.http.webapp_common import USER_PHOTOS_DIR, _build_photo_url
from app.api.http.webapp_schemas import (
    WebAppBankUpdateRead,
    WebAppBankUpdateWrite,
    WebAppPhoneUpdateRead,
    WebAppPhoneUpdateWrite,
    WebAppPhotoUploadRead,
)
from app.api.security.webapp_auth import WebAppIdentity, require_authenticated_principal
from app.db.dependencies import get_db_session
from app.db.repositories.user_repository import UserRepository

router = APIRouter()


def _normalize_phone(value: str) -> str | None:
    digits = "".join(ch for ch in value if ch.isdigit())
    if digits.startswith("7") and len(digits) == 11:
        return f"+{digits}"
    return None


def _normalize_bank_name(value: str) -> str | None:
    normalized = " ".join(value.split()).strip()
    if not normalized:
        return None
    return normalized[:1].upper() + normalized[1:].lower()


@router.post(
    "/me/photo",
    response_model=WebAppPhotoUploadRead,
    status_code=status.HTTP_201_CREATED,
)
async def upload_webapp_user_photo_by_platform(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_db_session),
    principal: WebAppIdentity = Depends(require_authenticated_principal),
) -> WebAppPhotoUploadRead:
    user = await UserRepository(session).get_by_row_id(int(principal.user_row_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only image files are supported"
        )

    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty file")
    if len(image_bytes) > 8 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image is too large")

    try:
        image = Image.open(BytesIO(image_bytes))
        image = ImageOps.exif_transpose(image).convert("RGB")
        image.thumbnail((1200, 1200))
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid image file"
        ) from error

    output_name = f"{user.row_id}.webp"
    output_rel_path = f"user_photos/{output_name}"
    output_path = USER_PHOTOS_DIR / output_name
    image.save(output_path, format="WEBP", quality=88, method=6)

    user.photo_path = output_rel_path
    user.updated_at = datetime.utcnow()
    await session.commit()
    await session.refresh(user)

    photo_url = _build_photo_url(user)
    if photo_url is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Photo url was not generated"
        )
    return WebAppPhotoUploadRead(photo_url=photo_url)


@router.post("/me/phone", response_model=WebAppPhoneUpdateRead)
async def update_webapp_user_phone_by_platform(
    payload: WebAppPhoneUpdateWrite,
    session: AsyncSession = Depends(get_db_session),
    principal: WebAppIdentity = Depends(require_authenticated_principal),
) -> WebAppPhoneUpdateRead:
    user = await UserRepository(session).get_by_row_id(int(principal.user_row_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    normalized_phone = _normalize_phone(payload.tel_number)
    if normalized_phone is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid phone number")

    user.tel_number = normalized_phone
    await session.commit()
    await session.refresh(user)
    return WebAppPhoneUpdateRead(tel_number=normalized_phone)


@router.post("/me/bank", response_model=WebAppBankUpdateRead)
async def update_webapp_user_bank_by_platform(
    payload: WebAppBankUpdateWrite,
    session: AsyncSession = Depends(get_db_session),
    principal: WebAppIdentity = Depends(require_authenticated_principal),
) -> WebAppBankUpdateRead:
    user = await UserRepository(session).get_by_row_id(int(principal.user_row_id))
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    normalized_bank = _normalize_bank_name(payload.bank_name)
    if normalized_bank is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid bank name")

    user.bank_name = normalized_bank
    await session.commit()
    await session.refresh(user)
    return WebAppBankUpdateRead(bank_name=normalized_bank)
