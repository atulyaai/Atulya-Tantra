"""Browser Automation — Playwright-based, free, CPU-based. Control any website/device."""
from __future__ import annotations

import base64
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class BrowserResult:
    success: bool
    url: str = ""
    title: str = ""
    content: str = ""
    screenshot_base64: str = ""
    links: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class BrowserAutomation:
    """Browser automation using Playwright (free, CPU-based)."""

    def __init__(self, headless: bool = True, output_dir: str = "config/browser"):
        self.headless = headless
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._browser = None
        self._context = None
        self._page = None
        self._history: list[BrowserResult] = []

    async def start(self):
        """Start browser instance."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(headless=self.headless)
            self._context = await self._browser.new_context()
            self._page = await self._context.new_page()
        except ImportError:
            logger.warning("Playwright not installed. Install with: pip install playwright && playwright install")
            self._browser = None

    async def stop(self):
        """Stop browser."""
        if self._browser:
            await self._browser.close()
        if hasattr(self, "_playwright"):
            await self._playwright.stop()

    async def navigate(self, url: str, wait_until: str = "domcontentloaded") -> BrowserResult:
        """Navigate to URL."""
        if not self._page:
            await self.start()
        try:
            await self._page.goto(url, wait_until=wait_until, timeout=30000)
            title = await self._page.title()
            content = await self._page.inner_text("body")
            links = await self._page.eval_on_selector_all("a[href]", "els => els.map(e => ({text: e.innerText, href: e.href}))")
            result = BrowserResult(
                success=True, url=url, title=title, content=content[:5000],
                links=links or [], metadata={"timestamp": time.time()},
            )
        except Exception as e:
            result = BrowserResult(success=False, url=url, metadata={"error": str(e)})
        self._history.append(result)
        return result

    async def screenshot(self, url: str | None = None, full_page: bool = False, save_path: str | None = None) -> str:
        """Take screenshot."""
        if not self._page:
            await self.start()
        if url:
            await self.navigate(url)
        screenshot = await self._page.screenshot(full_page=full_page)
        screenshot_b64 = base64.b64encode(screenshot).decode()
        if save_path:
            Path(save_path).write_bytes(screenshot)
        return screenshot_b64

    async def extract_content(self, selector: str = "body") -> str:
        """Extract content from page."""
        if not self._page:
            return ""
        return await self._page.inner_text(selector)

    async def fill_form(self, selector: str, value: str) -> bool:
        """Fill form field."""
        if not self._page:
            return False
        await self._page.fill(selector, value)
        return True

    async def click(self, selector: str) -> bool:
        """Click element."""
        if not self._page:
            return False
        await self._page.click(selector)
        return True

    async def execute_js(self, script: str) -> Any:
        """Execute JavaScript."""
        if not self._page:
            return None
        return await self._page.evaluate(script)

    async def get_cookies(self) -> list[dict[str, Any]]:
        """Get cookies."""
        if not self._page:
            return []
        return await self._page.context.cookies()

    async def wait_for(self, selector: str, timeout: float = 10000) -> bool:
        """Wait for element."""
        if not self._page:
            return False
        try:
            await self._page.wait_for_selector(selector, timeout=int(timeout))
            return True
        except Exception:
            return False

    def get_stats(self) -> dict[str, Any]:
        return {"pages_visited": len(self._history), "last_url": self._history[-1].url if self._history else ""}
