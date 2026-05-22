import asyncio

from app.db.session import SessionFactory
from app.services.google_backup import full_replace_tables_to_google


async def main() -> None:
  async with SessionFactory() as session:
    await full_replace_tables_to_google(session=session)
  print("Done: all backup tables synced to Google (full replace).")


if __name__ == "__main__":
  asyncio.run(main())
