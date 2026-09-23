import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.bot.shared.identity import resolve_telegram_user_id, resolve_vk_user_id
from app.db.base import Base
from app.db.models.user import User


@pytest.mark.asyncio
async def test_platform_identity_resolvers_return_only_canonical_user_id() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[User.__table__])
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        user = User(
            name="Pending non-admin",
            telegram_id=11,
            vk_id=22,
            is_approved=False,
            is_admin=False,
        )
        session.add(user)
        await session.commit()
        expected_id = int(user.row_id)

    async with session_factory() as session:
        assert await resolve_telegram_user_id(session=session, telegram_id=11) == expected_id
        assert await resolve_vk_user_id(session=session, vk_id=22) == expected_id
        assert await resolve_telegram_user_id(session=session, telegram_id=999) is None
        assert await resolve_vk_user_id(session=session, vk_id=999) is None

    await engine.dispose()
