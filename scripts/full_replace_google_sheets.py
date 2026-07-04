import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionFactory
from app.services.google_backup import full_replace_tables_to_google


async def main() -> None:
  async with SessionFactory() as session:
    await full_replace_tables_to_google(session=session)
  print("Done: full replace sync to Google sheets (one table -> one sheet).")


if __name__ == "__main__":
  asyncio.run(main())
