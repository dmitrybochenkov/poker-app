from app.config.settings import settings
from app.db.models.user import User

USER_PHOTOS_DIR = settings.resolved_user_photos_dir
USER_PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def _build_static_url(path: str) -> str:
    base = settings.effective_api_base_url
    if base:
        return f"{base}/api/static/{path}"
    return f"/api/static/{path}"


def _build_photo_url(user: User) -> str | None:
    if not user.photo_path:
        return None
    version = int(user.updated_at.timestamp()) if user.updated_at is not None else 0
    return f"{_build_static_url(user.photo_path)}?v={version}"
