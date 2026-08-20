"""
browser_session.py

A lightweight wrapper around Playwright's synchronous API that manages the
lifecycle of a Chromium browser instance (launch, context/page creation, and
cleanup). Designed to be used either manually via start()/close() or as a
context manager via the `with` statement.
"""

import logging
from pathlib import Path
from typing import Any, Self

from playwright.sync_api import (
    Browser,
    BrowserContext,
    Page,
    Playwright,
    sync_playwright,
)

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


class BrowserSession:
    """
    Manages a single Playwright browser + browser context + page, handling
    setup and teardown so callers don't have to repeat Playwright boilerplate.

    Usage (manual):
        session = BrowserSession().start()
        session.page.goto("https://example.com")
        session.close()

    Usage (context manager):
        with BrowserSession() as session:
            session.page.goto("https://example.com")

    Usage with saved session:
        session = BrowserSession(storage_state="data/session.json").start()
    """

    def __init__(
        self,
        headless: bool = False,
        storage_state: str | Path | None = None,
        **launch_kwargs: Any,
    ):
        """
        Args:
            headless: Whether to launch Chromium without a visible UI window.
            storage_state: Path to a JSON file saved by ``context.storage_state()``.
                When provided, the browser context is created from this state
                (cookies + localStorage), skipping the login flow.
            **launch_kwargs: Extra kwargs forwarded to ``chromium.launch()``.
        """
        self.headless = headless
        self.storage_state = storage_state
        self.launch_kwargs = launch_kwargs

        self.playwright: Playwright | None = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None

    def start(self) -> Self:
        """
        Launches Chromium, opens a new browser context and page, and returns
        self so the call can be chained, e.g. ``session = BrowserSession().start()``.
        """
        self.playwright = sync_playwright().start()

        try:
            browser_options = {
                "headless": self.headless,
                "args": ["--disable-blink-features=AutomationControlled"],
                **self.launch_kwargs,
            }

            logger.info("Launching browser (headless=%s)", self.headless)

            self.browser = self.playwright.chromium.launch(**browser_options)

            context_options: dict[str, Any] = {
                "user_agent": DEFAULT_USER_AGENT,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
            }

            if self.storage_state:
                state_path = Path(self.storage_state)
                if state_path.exists():
                    logger.info("Loading session from %s", state_path)
                    context_options["storage_state"] = str(state_path)
                else:
                    logger.warning(
                        "Session file %s not found, starting fresh", state_path
                    )

            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
        except Exception as e:
            logger.error(e)
            self.close()
            raise
        return self

    def save_storage_state(self, path: str | Path) -> Path:
        """Save cookies + localStorage to a JSON file for later reuse."""
        if not self.context:
            raise RuntimeError("No active browser context to save")

        save_path = Path(path)
        save_path.parent.mkdir(parents=True, exist_ok=True)
        self.context.storage_state(path=str(save_path))
        logger.info("Session saved to %s", save_path)
        return save_path

    def close(self) -> None:
        """Closes the context/browser (if launched) and stops the Playwright driver."""
        logger.info("Closing browser")
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def __enter__(self) -> Self:
        """Supports ``with BrowserSession() as session:``."""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensures the browser is closed when exiting a ``with`` block."""
        self.close()
