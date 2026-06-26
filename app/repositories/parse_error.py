from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.parse_error import ParseError
from app.repositories.base import BaseRepository


class ParseErrorRepository(BaseRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        subscription_id: int,
        error_type: str,
        error_message: str,
    ) -> ParseError:
        parse_error = ParseError(
            subscription_id=subscription_id,
            error_type=error_type,
            error_message=error_message,
        )
        self._session.add(parse_error)
        await self._session.commit()
        await self._session.refresh(parse_error)
        return parse_error

    async def get_by_subscription_id(
        self,
        subscription_id: int,
    ) -> list[ParseError]:
        result = await self._session.execute(
            select(ParseError)
            .where(ParseError.subscription_id == subscription_id)
            .order_by(ParseError.created_at.desc()),
        )
        return list(result.scalars().all())
