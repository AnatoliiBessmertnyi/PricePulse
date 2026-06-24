from typing import TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelType = TypeVar(
    "ModelType",
    bound=Base,
)


class BaseRepository[ModelType: Base]:
    model: type[ModelType]

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, obj_id: int) -> ModelType | None:
        stmt = select(self.model).where(
            self.model.id == obj_id,
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    async def get_all(self) -> list[ModelType]:
        stmt = select(self.model)

        result = await self.session.execute(stmt)

        return list(result.scalars().all())

    async def create(self, **kwargs) -> ModelType:
        obj = self.model(**kwargs)

        self.session.add(obj)

        await self.session.flush()

        return obj

    async def delete(self, obj: ModelType) -> None:
        await self.session.delete(obj)
