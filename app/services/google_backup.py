import asyncio
import logging
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.inspection import inspect as sa_inspect

from app.config.settings import settings
from app.db.models.bet import Bet
from app.db.models.bet_tournament import BetTournament
from app.db.models.buyin_data import BuyinData
from app.db.models.poker import Poker
from app.db.models.poker_data import PokerData
from app.db.models.sync_state import SyncState

logger = logging.getLogger(__name__)

BACKUP_MODELS: list[type] = [
  Poker,
  PokerData,
  Bet,
  BuyinData,
  BetTournament,
]


def _normalize_value(value: Any) -> Any:
  if value is None:
    return ""
  if isinstance(value, bool):
    return int(value)
  if isinstance(value, datetime):
    return value.isoformat(sep=" ", timespec="seconds")
  if isinstance(value, date):
    return value.isoformat()
  if isinstance(value, Enum):
    return value.value
  return value


def _build_sheets_service():
  from google.oauth2.service_account import Credentials
  from googleapiclient.discovery import build

  creds_path = Path(settings.google_credentials_path).expanduser().resolve()
  credentials = Credentials.from_service_account_file(
    str(creds_path),
    scopes=["https://www.googleapis.com/auth/spreadsheets"],
  )
  return build("sheets", "v4", credentials=credentials, cache_discovery=False)


def _ensure_sheet_exists_sync(*, service, spreadsheet_id: str, sheet_name: str) -> None:
  meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
  existing_sheets = {
    str(item.get("properties", {}).get("title", "")).strip()
    for item in meta.get("sheets", [])
  }
  if sheet_name in existing_sheets:
    return
  service.spreadsheets().batchUpdate(
    spreadsheetId=spreadsheet_id,
    body={
      "requests": [
        {
          "addSheet": {
            "properties": {"title": sheet_name},
          }
        }
      ]
    },
  ).execute()


def _ensure_header_sync(
  *,
  service,
  spreadsheet_id: str,
  sheet_name: str,
  columns: list[str],
) -> None:
  resp = service.spreadsheets().values().get(
    spreadsheetId=spreadsheet_id,
    range=f"{sheet_name}!1:1",
  ).execute()
  values = resp.get("values", [])
  if values and values[0]:
    return
  service.spreadsheets().values().update(
    spreadsheetId=spreadsheet_id,
    range=f"{sheet_name}!A1",
    valueInputOption="RAW",
    body={"values": [columns]},
  ).execute()


def _read_row_id_map_sync(*, service, spreadsheet_id: str, sheet_name: str) -> dict[int, int]:
  resp = service.spreadsheets().values().get(
    spreadsheetId=spreadsheet_id,
    range=f"{sheet_name}!A2:A",
  ).execute()
  values = resp.get("values", [])
  mapping: dict[int, int] = {}
  for idx, row in enumerate(values, start=2):
    if not row:
      continue
    raw = str(row[0]).strip()
    if not raw:
      continue
    try:
      mapping[int(raw)] = idx
    except Exception:
      continue
  return mapping


def _append_row_sync(
  *,
  service,
  spreadsheet_id: str,
  sheet_name: str,
  row_values: list[Any],
) -> None:
  service.spreadsheets().values().append(
    spreadsheetId=spreadsheet_id,
    range=f"{sheet_name}!A1",
    valueInputOption="RAW",
    insertDataOption="INSERT_ROWS",
    body={"values": [row_values]},
  ).execute()


def _update_row_sync(
  *,
  service,
  spreadsheet_id: str,
  sheet_name: str,
  row_number: int,
  row_values: list[Any],
) -> None:
  service.spreadsheets().values().update(
    spreadsheetId=spreadsheet_id,
    range=f"{sheet_name}!A{row_number}",
    valueInputOption="RAW",
    body={"values": [row_values]},
  ).execute()


async def _get_sync_state(session: AsyncSession, table_name: str) -> SyncState:
  state = await session.get(SyncState, table_name)
  if state is not None:
    return state
  state = SyncState(
    table_name=table_name,
    last_synced_row_id=0,
    last_synced_updated_at=None,
  )
  session.add(state)
  await session.flush()
  return state


async def _read_changed_rows(session: AsyncSession, model: type, state: SyncState) -> list[Any]:
  updated_col = getattr(model, "updated_at")
  stmt = (
    select(model)
    .where(
      or_(
        model.row_id > int(state.last_synced_row_id or 0),
        updated_col > state.last_synced_updated_at if state.last_synced_updated_at is not None else False,
      )
    )
    .order_by(model.row_id.asc())
  )
  result = await session.execute(stmt)
  return list(result.scalars().all())


async def backup_tables_to_google(session: AsyncSession) -> None:
  if not settings.google_backup_enabled:
    return
  if not settings.google_spreadsheet_id.strip():
    logger.warning("Google backup is enabled, but GOOGLE_SPREADSHEET_ID is empty.")
    return

  service = await asyncio.to_thread(_build_sheets_service)
  spreadsheet_id = settings.google_spreadsheet_id

  for model in BACKUP_MODELS:
    table_name = str(model.__tablename__)
    mapper = sa_inspect(model)
    columns = [column.key for column in mapper.columns]
    state = await _get_sync_state(session=session, table_name=table_name)
    changed_rows = await _read_changed_rows(session=session, model=model, state=state)
    if not changed_rows:
      continue

    await asyncio.to_thread(
      _ensure_sheet_exists_sync,
      service=service,
      spreadsheet_id=spreadsheet_id,
      sheet_name=table_name,
    )
    await asyncio.to_thread(
      _ensure_header_sync,
      service=service,
      spreadsheet_id=spreadsheet_id,
      sheet_name=table_name,
      columns=columns,
    )
    row_map = await asyncio.to_thread(
      _read_row_id_map_sync,
      service=service,
      spreadsheet_id=spreadsheet_id,
      sheet_name=table_name,
    )

    max_row_id = int(state.last_synced_row_id or 0)
    max_updated_at = state.last_synced_updated_at
    for row in changed_rows:
      row_values = [_normalize_value(getattr(row, col)) for col in columns]
      row_id = int(getattr(row, "row_id"))
      row_updated_at = getattr(row, "updated_at", None)
      target_row = row_map.get(row_id)
      if target_row is None:
        await asyncio.to_thread(
          _append_row_sync,
          service=service,
          spreadsheet_id=spreadsheet_id,
          sheet_name=table_name,
          row_values=row_values,
        )
      else:
        await asyncio.to_thread(
          _update_row_sync,
          service=service,
          spreadsheet_id=spreadsheet_id,
          sheet_name=table_name,
          row_number=target_row,
          row_values=row_values,
        )
      if row_id > max_row_id:
        max_row_id = row_id
      if row_updated_at is not None and (max_updated_at is None or row_updated_at > max_updated_at):
        max_updated_at = row_updated_at

    state.last_synced_row_id = max_row_id
    state.last_synced_updated_at = max_updated_at
    state.updated_at = datetime.utcnow()

  await session.commit()


async def dump_all_tables_to_single_sheet_test(session: AsyncSession, *, sheet_name: str = "test") -> None:
  if not settings.google_spreadsheet_id.strip():
    raise RuntimeError("GOOGLE_SPREADSHEET_ID is empty.")

  service = await asyncio.to_thread(_build_sheets_service)
  spreadsheet_id = settings.google_spreadsheet_id
  await asyncio.to_thread(
    _ensure_sheet_exists_sync,
    service=service,
    spreadsheet_id=spreadsheet_id,
    sheet_name=sheet_name,
  )

  values: list[list[Any]] = []
  for model in BACKUP_MODELS:
    table_name = str(model.__tablename__)
    mapper = sa_inspect(model)
    columns = [column.key for column in mapper.columns]
    result = await session.execute(select(model).order_by(model.row_id.asc()))
    rows = list(result.scalars().all())
    values.append([f"=== {table_name} ==="])
    values.append(columns)
    for row in rows:
      values.append([_normalize_value(getattr(row, col)) for col in columns])
    values.append([])

  await asyncio.to_thread(
    lambda: service.spreadsheets().values().update(
      spreadsheetId=spreadsheet_id,
      range=f"{sheet_name}!A1",
      valueInputOption="RAW",
      body={"values": values},
    ).execute()
  )
