import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
  sys.path.insert(0, str(BACKEND_DIR))

from app.db.session import SessionFactory
from app.services.google_backup import dump_all_tables_to_single_sheet_test


async def main() -> None:
  async with SessionFactory() as session:
    await dump_all_tables_to_single_sheet_test(session=session, sheet_name="test")
  print("Done: dumped backup tables to Google sheet tab 'test'.")


if __name__ == "__main__":
  asyncio.run(main())
