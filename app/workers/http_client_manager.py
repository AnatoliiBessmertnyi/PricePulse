import httpx

_http_client: httpx.AsyncClient | None = None


def get_http_client() -> httpx.AsyncClient:
    """Возвращает singleton httpx клиент."""
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            timeout=30.0,
            follow_redirects=True,
        )
    return _http_client


async def close_http_client() -> None:
    """Закрывает httpx клиент."""
    global _http_client
    if _http_client is not None:
        await _http_client.aclose()
        _http_client = None
