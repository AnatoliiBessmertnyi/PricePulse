from abc import ABC, abstractmethod

from app.parsers.schemas import ProductData


class BaseParser(ABC):
    @abstractmethod
    async def parse(
        self,
        product_url: str,
    ) -> ProductData:
        ...