from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
  app_name: str = "Poker App"
  app_host: str = "127.0.0.1"
  app_port: int = 8000
  debug: bool = False
  public_base_url: str = ""

  telegram_bot_token: str = ""
  telegram_webhook_secret: str = ""

  vk_group_token: str = ""
  vk_confirmation_token: str = ""
  vk_secret_key: str = ""
  vk_api_version: str = "5.199"

  database_url: str = "sqlite+aiosqlite:///./poker_app.db"
  google_backup_enabled: bool = False
  google_spreadsheet_id: str = ""
  google_credentials_path: str = "credentials.json"

  model_config = SettingsConfigDict(
    env_file=".env",
    env_file_encoding="utf-8",
    extra="ignore",
  )


settings = Settings()
