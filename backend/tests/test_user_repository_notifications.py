from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.models.user import User
from app.db.repositories.user_repository import UserRepository


async def test_notification_recipient_queries_preserve_platform_preference() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all, tables=[User.__table__])

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        session.add_all(
            [
                User(
                    name="Telegram",
                    telegram_id=11,
                    vk_id=21,
                    notification_platform="tg",
                    is_approved=True,
                ),
                User(
                    name="VK",
                    telegram_id=12,
                    vk_id=22,
                    notification_platform="vk",
                    is_approved=True,
                ),
                User(
                    name="Pending",
                    telegram_id=13,
                    notification_platform="tg",
                    is_approved=False,
                ),
                User(
                    name="Legacy",
                    vk_id=24,
                    notification_platform=None,
                    is_approved=True,
                ),
            ]
        )
        await session.commit()

        repository = UserRepository(session)
        assert await repository.list_approved_tg_ids() == [11]
        assert await repository.list_approved_vk_ids() == [22]

    await engine.dispose()
