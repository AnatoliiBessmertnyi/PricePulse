import asyncio

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.repositories.user import UserRepository


async def main():
    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)

        await repo.create(
            chat_id=123456789,
            username="test_user",
        )

        await session.commit()

        found = await repo.get_by_chat_id(
            123456789,
        )

        print(found.id)
        print(found.chat_id)
        print(found.username)

        stmt = select(User).where(
            User.chat_id == 123456789,
        )

        result = await session.execute(stmt)

        db_user = result.scalar_one()

        await session.delete(db_user)

        await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
