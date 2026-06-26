class ParserError(Exception):
    """Базовое исключение для ошибок парсинга."""
    pass


class ProductDataNotFoundError(ParserError):
    """Товар не найден или страница недоступна."""
    pass


class PriceNotFoundError(ParserError):
    """Цена не найдена на странице товара."""
    pass
