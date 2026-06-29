import re

import structlog

logger = structlog.get_logger()


def extract_url_from_text(text: str) -> str | None:
    """
    Извлекает URL из текста сообщения.
    
    Поддерживает:
    - Чистые URL: "https://ozon.ru/product/..."
    - Текст с URL: "Смотри что я нашел! https://ozon.ru/product/..."
    
    Args:
        text: Текст сообщения от пользователя
        
    Returns:
        Извлечённый URL или None, если URL не найден
    """
    # Регулярка для извлечения URL
    url_pattern = r'https?://[^\s]+'
    matches = re.findall(url_pattern, text)
    
    if not matches:
        logger.warning("url_not_found", text=text)
        return None
    
    # Берём первый найденный URL
    url = matches[0]
    
    # Удаляем возможные trailing символы (запятые, точки)
    url = url.rstrip('.,;:!?')
    
    logger.info("url_extracted", url=url, original_text=text)
    return url


def validate_marketplace_url(url: str) -> tuple[bool, str | None]:
    """
    Валидирует URL и определяет маркетплейс.
    
    Args:
        url: URL для валидации
        
    Returns:
        (is_valid, marketplace_name)
    """
    if not url:
        return False, None
    
    # Поддерживаемые маркетплейсы
    supported_marketplaces = {
        'ozon.ru': 'ozon',
        'www.ozon.ru': 'ozon',
    }
    
    # Извлекаем домен из URL
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        domain = parsed.netloc.lower()
    except Exception as e:
        logger.error("url_parse_error", url=url, error=str(e))
        return False, None
    
    marketplace = supported_marketplaces.get(domain)
    
    if marketplace:
        logger.info("url_validated", url=url, marketplace=marketplace)
        return True, marketplace
    
    logger.warning("unsupported_marketplace", url=url, domain=domain)
    return False, None


def clean_and_validate_url(text: str) -> tuple[str | None, str | None]:
    """
    Извлекает URL из текста и валидирует его.
    
    Args:
        text: Текст сообщения от пользователя
        
    Returns:
        (url, marketplace) или (None, None) если невалидно
    """
    url = extract_url_from_text(text)
    if not url:
        return None, None
    
    is_valid, marketplace = validate_marketplace_url(url)
    if not is_valid:
        return None, None
    
    return url, marketplace
