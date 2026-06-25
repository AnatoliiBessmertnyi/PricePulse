from app.parsers.base import BaseParser
from app.parsers.constants import Marketplace
from app.parsers.ozon import OzonParser


class ParserFactory:
    @staticmethod
    def get_parser(
        marketplace: Marketplace,
    ) -> BaseParser:
        match marketplace:
            case Marketplace.OZON:
                return OzonParser()

        raise ValueError(
            f"Unsupported marketplace: {marketplace}",
        )
