from playwright.async_api import Page, async_playwright


async def get_page() -> Page:
    """Создает новый браузер и страницу для каждой задачи."""
    playwright = await async_playwright().start()
    
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ],
    )
    
    context = await browser.new_context(
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        viewport={"width": 1920, "height": 1080},
        locale="ru-RU",
        timezone_id="Europe/Moscow",
    )
    
    page = await context.new_page()
    
    # Сохраняем ссылки для закрытия
    page._browser = browser
    page._playwright = playwright
    page._context = context
    
    return page


async def close_page(page: Page) -> None:
    """Закрывает страницу, контекст, браузер и Playwright."""
    try:
        await page.close()
    except Exception:
        pass
    
    try:
        if hasattr(page, "_context"):
            await page._context.close()
    except Exception:
        pass
    
    try:
        if hasattr(page, "_browser"):
            await page._browser.close()
    except Exception:
        pass
    
    try:
        if hasattr(page, "_playwright"):
            await page._playwright.stop()
    except Exception:
        pass
