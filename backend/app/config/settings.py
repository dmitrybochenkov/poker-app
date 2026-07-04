from pathlib import Path
from urllib.parse import urlsplit

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
  app_name: str = "Poker App"
  app_host: str = "127.0.0.1"
  app_port: int = 8000
  debug: bool = False
  public_base_url: str = ""
  cors_allowed_origins: str = ""

  telegram_bot_token: str = ""
  telegram_webhook_secret: str = ""

  vk_group_token: str = ""
  vk_confirmation_token: str = ""
  vk_secret_key: str = ""
  vk_api_version: str = "5.199"

  data_dir: str = "../data"
  logs_dir: str = "../logs"
  static_dir: str = "../data/static"
  user_photos_dir: str = "../data/static/user_photos"
  webapp_dist_dir: str = "../webapp/dist"
  site_dist_dir: str = "../site/dist"
  database_url: str = ""
  google_backup_enabled: bool = False
  google_spreadsheet_id: str = ""
  google_credentials_path: str = "../credentials.json"

  model_config = SettingsConfigDict(
    env_file=(".env", "../.env"),
    env_file_encoding="utf-8",
    extra="ignore",
  )

  @staticmethod
  def _resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
      return path
    return (BACKEND_ROOT / path).resolve()

  @staticmethod
  def _normalize_url(value: str) -> str:
    return value.strip().rstrip("/")

  @staticmethod
  def _normalize_origin(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
      return ""
    parts = urlsplit(normalized)
    if parts.scheme and parts.netloc:
      return f"{parts.scheme}://{parts.netloc}"
    return normalized

  @property
  def resolved_data_dir(self) -> Path:
    return self._resolve_path(self.data_dir)

  @property
  def resolved_logs_dir(self) -> Path:
    return self._resolve_path(self.logs_dir)

  @property
  def resolved_static_dir(self) -> Path:
    return self._resolve_path(self.static_dir)

  @property
  def resolved_user_photos_dir(self) -> Path:
    return self._resolve_path(self.user_photos_dir)

  @property
  def resolved_webapp_dist_dir(self) -> Path:
    return self._resolve_path(self.webapp_dist_dir)

  @property
  def resolved_site_dist_dir(self) -> Path:
    return self._resolve_path(self.site_dist_dir)

  @property
  def resolved_google_credentials_path(self) -> Path:
    return self._resolve_path(self.google_credentials_path)

  @property
  def effective_public_base_url(self) -> str:
    return self._normalize_url(self.public_base_url)

  @property
  def effective_api_base_url(self) -> str:
    return self.effective_public_base_url

  @property
  def effective_webapp_base_url(self) -> str:
    public = self.effective_public_base_url
    if not public:
      return ""
    return f"{public}/app"

  @property
  def effective_cors_origins(self) -> list[str]:
    origins: list[str] = []
    for raw in self.cors_allowed_origins.split(","):
      normalized = self._normalize_origin(raw)
      if normalized and normalized not in origins:
        origins.append(normalized)

    webapp_origin = self._normalize_origin(self.effective_webapp_base_url)
    if webapp_origin and webapp_origin not in origins:
      origins.append(webapp_origin)

    public_origin = self._normalize_origin(self.effective_public_base_url)
    if public_origin and public_origin not in origins:
      origins.append(public_origin)

    return origins

  @property
  def effective_database_url(self) -> str:
    configured = self.database_url.strip()
    if configured:
      return configured
    db_path = self.resolved_data_dir / "poker_app.db"
    return f"sqlite+aiosqlite:///{db_path.as_posix()}"

  @property
  def effective_sync_database_url(self) -> str:
    return self.effective_database_url.replace("+aiosqlite", "")


settings = Settings()
