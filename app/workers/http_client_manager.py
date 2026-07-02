from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.logging import get_logger

logger = get_logger(__name__)

# Глобальные переменные уровня процесса
# Каждый worker процесс имеет свои копии
_browser: Browser | None = None
_context: BrowserContext | None = None
_page: Page | None = None
_playwright = None


async def get_page() -> Page:
    """
    Получить страницу из браузера текущего процесса.

    Каждый worker процесс имеет свой браузер.
    Браузер создается при первом вызове и переиспользуется.
    """
    global _browser, _context, _page, _playwright

    # Если уже есть — возвращаем
    if _page is not None:
        logger.info("http_client_reusing_browser")
        return _page

    logger.info("http_client_launching_browser")

    # Запускаем Playwright (один раз на процесс)
    _playwright = await async_playwright().start()

    # Запускаем браузер
    _browser = await _playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-blink-features=AutomationControlled",
        ],
    )
    logger.info("http_client_browser_launched")

    # Создаем контекст
    _context = await _browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )

    # Маскировка webdriver
    await _context.add_init_script(
        """
        Object.defineProperty(navigator, 'webdriver', {
            get: () => undefined
        });
    """
    )

    # Создаем страницу
    _page = await _context.new_page()
    logger.info("http_client_browser_ready")

    return _page


async def close_page(page: Page) -> None:
    """
    Закрыть браузер текущего процесса.

    Вызывается Celery через worker_max_tasks_per_child=1.
    После этого процесс перезапускается с чистым браузером.
    """
    global _browser, _context, _page, _playwright

    logger.info("http_client_closing_browser")

    try:
        if _page:
            await _page.close()
            logger.info("http_client_page_closed")
    except Exception:
        pass

    try:
        if _context:
            await _context.close()
            logger.info("http_client_context_closed")
    except Exception:
        pass

    try:
        if _browser:
            await _browser.close()
            logger.info("http_client_browser_closed")
    except Exception:
        pass

    try:
        if _playwright:
            await _playwright.stop()
            logger.info("http_client_playwright_stopped")
    except Exception:
        pass

    # Сбрасываем глобальные переменные
    _page = None
    _context = None
    _browser = None
    _playwright = None
