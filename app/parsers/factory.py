from app.parsers.base import BaseParser
from app.parsers.constants import Marketplace
from app.parsers.http_client import MarketplaceHttpClient
from app.parsers.ozon import OzonParser


class ParserFactory:
    def __init__(self, http_client: MarketplaceHttpClient) -> None:
        self._http_client = http_client

    def get_parser(self, marketplace: Marketplace) -> BaseParser:
        match marketplace:
            case Marketplace.OZON:
                return OzonParser(http_client=self._http_client)
            case _:
                raise ValueError(f"Unsupported marketplace: {marketplace}")
