from sqlalchemy import select

from app.models.user import User
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_chat_id(
        self,
        chat_id: int,
    ) -> User | None:
        stmt = select(User).where(
            User.chat_id == chat_id,
        )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()
