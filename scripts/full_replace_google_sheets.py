import asyncio

from app.db.session import SessionFactory
from app.services.google_backup import full_replace_tables_to_google


async def main() -> None:
  async with SessionFactory() as session:
    await full_replace_tables_to_google(session=session)
  print("Done: full replace sync to Google sheets (one table -> one sheet).")


if __name__ == "__main__":
  asyncio.run(main())
