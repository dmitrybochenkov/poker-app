from fastapi import APIRouter, HTTPException, status

from app.config.settings import settings

router = APIRouter(prefix="/webhooks/vk", tags=["vk"])


@router.post("")
async def vk_webhook(payload: dict) -> str | dict[str, bool]:
  event_type = payload.get("type")

  if payload.get("secret") and settings.vk_secret_key:
    if payload["secret"] != settings.vk_secret_key:
      raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Invalid VK secret",
      )

  if event_type == "confirmation":
    return settings.vk_confirmation_token

  return {"ok": True}
