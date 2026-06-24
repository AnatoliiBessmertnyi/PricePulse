from app.models.price_history import PriceHistory
from app.repositories.base import BaseRepository


class PriceHistoryRepository(BaseRepository[PriceHistory]):
    model = PriceHistory
