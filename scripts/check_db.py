import asyncio

from sqlalchemy import text

from app.core.database import engine


async def main() -> None:
    async with engine.begin() as conn:
        result = await conn.execute(text("SELECT 1"))

        print(result.scalar())


if __name__ == "__main__":
    asyncio.run(main())
