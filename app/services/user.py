from app.repositories.user import UserRepository


class UserService:
    def __init__(
        self,
        user_repository: UserRepository,
    ):
        self.user_repository = user_repository

    async def get_or_create_user(
        self,
        chat_id: int,
        username: str | None,
    ):
        user = await self.user_repository.get_by_chat_id(
            chat_id,
        )

        if user:
            return user

        return await self.user_repository.create(
            chat_id=chat_id,
            username=username,
        )
