from playwright.async_api import Browser, Page, Playwright, async_playwright

_browser: Browser | None = None
_playwright: Playwright | None = None


async def get_browser() -> Browser:
    """Возвращает singleton браузер."""
    global _browser, _playwright
    if _browser is None:
        _playwright = await async_playwright().start()
        _browser = await _playwright.chromium.launch(
            headless=True, args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
    return _browser


async def get_page() -> Page:
    """Создает новую страницу в браузере."""
    browser = await get_browser()
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        locale="ru-RU",
    )
    return await context.new_page()


async def close_browser() -> None:
    """Закрывает браузер и Playwright."""
    global _browser, _playwright
    if _browser is not None:
        await _browser.close()
        _browser = None
    if _playwright is not None:
        await _playwright.stop()
        _playwright = None
