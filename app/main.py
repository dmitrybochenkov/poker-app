from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.http.health import router as health_router
from app.api.http.registration import router as registration_router
from app.api.http.telegram_webhook import router as telegram_webhook_router
from app.api.http.users import router as users_router
from app.api.http.vk_webhook import router as vk_webhook_router
from app.api.http.webapp import router as webapp_router
from app.bot.telegram.runtime import setup_telegram_webhook, shutdown_telegram_bot
from app.config.settings import settings
from app.db.session import finalize_database


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
  await setup_telegram_webhook()
  yield
  await shutdown_telegram_bot()
  await finalize_database()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

def _normalize_origin(raw: str) -> str:
  value = raw.strip().rstrip("/")
  if not value:
    return ""
  parts = urlsplit(value)
  if parts.scheme and parts.netloc:
    return f"{parts.scheme}://{parts.netloc}"
  return value


cors_origins = []
for origin in settings.cors_allowed_origins.split(","):
  normalized = _normalize_origin(origin)
  if normalized and normalized not in cors_origins:
    cors_origins.append(normalized)
if settings.webapp_base_url:
  webapp_origin = _normalize_origin(settings.webapp_base_url)
  if webapp_origin not in cors_origins:
    cors_origins.append(webapp_origin)

if cors_origins:
  app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
  )

static_dir = settings.resolved_static_dir
static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/api/static", StaticFiles(directory=static_dir), name="api-static")

app.include_router(health_router)
app.include_router(registration_router)
app.include_router(telegram_webhook_router)
app.include_router(vk_webhook_router)
app.include_router(users_router)
app.include_router(webapp_router)


def _resolve_dist_asset(dist_dir: Path, relative_path: str) -> Path | None:
  if not relative_path or relative_path.endswith("/"):
    return None
  candidate = (dist_dir / relative_path).resolve()
  try:
    candidate.relative_to(dist_dir.resolve())
  except ValueError:
    return None
  if candidate.is_file():
    return candidate
  return None


@app.get("/", include_in_schema=False, response_model=None)
async def site_index() -> FileResponse | HTMLResponse:
  site_index_file = settings.resolved_site_dist_dir / "index.html"
  if site_index_file.is_file():
    return FileResponse(site_index_file)
  return HTMLResponse(
    """
    <html lang="ru">
      <head><meta charset="utf-8"><title>Poker u Molodogo</title></head>
      <body style="font-family: sans-serif; padding: 24px;">
        <h1>Poker u Molodogo</h1>
        <p>Backend is online.</p>
        <p>WebApp: <a href="/app/">/app/</a></p>
        <p>Health: <a href="/api/health">/api/health</a></p>
      </body>
    </html>
    """.strip()
  )


@app.get("/app", include_in_schema=False)
async def webapp_index_redirect() -> FileResponse | HTMLResponse:
  webapp_index_file = settings.resolved_webapp_dist_dir / "index.html"
  if webapp_index_file.is_file():
    return FileResponse(webapp_index_file)
  return HTMLResponse("<h1>WebApp build not found</h1>", status_code=503)


@app.get("/app/{full_path:path}", include_in_schema=False)
async def webapp_assets(full_path: str) -> FileResponse | HTMLResponse:
  dist_dir = settings.resolved_webapp_dist_dir
  if not dist_dir.exists():
    return HTMLResponse("<h1>WebApp build not found</h1>", status_code=503)

  asset_file = _resolve_dist_asset(dist_dir, full_path)
  if asset_file is not None:
    return FileResponse(asset_file)

  index_file = dist_dir / "index.html"
  if index_file.is_file():
    return FileResponse(index_file)
  return HTMLResponse("<h1>WebApp build not found</h1>", status_code=503)
