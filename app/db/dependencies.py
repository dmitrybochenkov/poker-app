from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import SessionFactory


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
  async with SessionFactory() as session:
    yield session
