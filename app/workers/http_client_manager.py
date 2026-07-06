from playwright.async_api import Browser, BrowserContext, Page, async_playwright

from app.core.logging import get_logger

logger = get_logger(__name__)


class ProcessBrowser:
    """
    Singleton на процесс для управления браузером Playwright.

    Каждый Celery worker процесс имеет свой экземпляр.
    Браузер создается при первом вызове и переиспользуется.
    """

    _instance: "ProcessBrowser | None" = None

    def __new__(cls) -> "ProcessBrowser":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False

        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._playwright = None
        self._initialized = True

    async def get_page(self) -> Page:
        """
        Получить страницу из браузера текущего процесса.

        Каждый worker процесс имеет свой браузер.
        Браузер создается при первом вызове и переиспользуется.
        """
        if self._page is not None:
            logger.info("http_client_reusing_browser")
            return self._page

        logger.info("http_client_launching_browser")
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
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
        self._context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            locale="ru-RU",
            timezone_id="Europe/Moscow",
        )

        await self._context.add_init_script(
            """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            """
        )

        self._page = await self._context.new_page()
        logger.info("http_client_browser_ready")
        return self._page

    async def close(self) -> None:
        """
        Закрыть браузер текущего процесса.

        Вызывается Celery через worker_max_tasks_per_child=1.
        После этого процесс перезапускается с чистым браузером.
        """
        logger.info("http_client_closing_browser")

        try:
            if self._page:
                await self._page.close()
                logger.info("http_client_page_closed")
        except Exception as e:
            logger.debug("http_client_page_close_failed", error=str(e))

        try:
            if self._context:
                await self._context.close()
                logger.info("http_client_context_closed")
        except Exception as e:
            logger.debug("http_client_context_close_failed", error=str(e))

        try:
            if self._browser:
                await self._browser.close()
                logger.info("http_client_browser_closed")
        except Exception as e:
            logger.debug("http_client_browser_close_failed", error=str(e))

        try:
            if self._playwright:
                await self._playwright.stop()
                logger.info("http_client_playwright_stopped")
        except Exception as e:
            logger.debug("http_client_playwright_close_failed", error=str(e))

        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None


def get_process_browser() -> ProcessBrowser:
    """Получить singleton экземпляр ProcessBrowser для текущего процесса."""
    return ProcessBrowser()


async def get_page() -> Page:
    """
    Получить страницу из браузера текущего процесса.

    Каждый worker процесс имеет свой браузер.
    Браузер создается при первом вызове и переиспользуется.
    """
    return await get_process_browser().get_page()


async def close_page(_page: Page) -> None:
    """
    Закрыть браузер текущего процесса.

    Вызывается Celery через worker_max_tasks_per_child=1.
    После этого процесс перезапускается с чистым браузером.
    """
    await get_process_browser().close()
