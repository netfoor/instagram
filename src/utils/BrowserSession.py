"""
browser_session.py

A lightweight wrapper around Playwright's synchronous API that manages the
lifecycle of a Chromium browser instance (launch, context/page creation, and
cleanup). Designed to be used either manually via start()/close() or as a
context manager via the `with` statement.
"""

from typing import Any, Optional
import logging

from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Playwright

# Configure root logging once at import time. Note: basicConfig() only takes
# effect if no handlers have been configured yet elsewhere in the app.
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# A realistic desktop Chrome user-agent string, used to reduce the chance of
# the browser being flagged as automated/headless by target websites.
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
    """

    def __init__(self, headless: bool = False, incognito: bool = False, **launch_kwargs: Any):
        """
        Args:
            headless: Whether to launch Chromium without a visible UI window.
            incognito: Reserved for toggling private/incognito-style browsing.
                Each Playwright BrowserContext is already isolated (its own
                cookies/storage) by default, so this flag is currently stored
                for callers' reference but doesn't change context creation.
            **launch_kwargs: Extra kwargs forwarded to `chromium.launch()`,
                merged into (and able to override) the default browser_options
                built in start().
        """
        self.headless = headless
        self.incognito = incognito
        self.launch_kwargs = launch_kwargs

        # The running Playwright driver instance; created in start(),
        # stopped in close().
        self.playwright: Optional[Playwright] = None

        # The launched Browser process.
        self.browser: Optional[Browser] = None

        # The isolated BrowserContext (cookies/storage/session) created from
        # `self.browser`.
        self.context: Optional[BrowserContext] = None

        self.page: Optional[Page] = None

    def start(self) -> "BrowserSession":
        """
        Launches Chromium, opens a new browser context and page, and returns
        self so the call can be chained, e.g. `session = BrowserSession().start()`.
        """
        # Start the Playwright driver process (must be paired with .stop() in close()).
        self.playwright = sync_playwright().start()
        
        try:
            browser_options = {
                "headless": self.headless,
                # Suppresses the `navigator.webdriver` flag that basic
                # bot-detection scripts check for.
                "args": ["--disable-blink-features=AutomationControlled"],
                # Lets callers override or extend any option above (e.g. proxy,
                # executable_path, slow_mo) via constructor kwargs.
                **self.launch_kwargs,
            }

            logger.info(f"Launching browser (headless={self.headless}, incognito={self.incognito})")

            self.browser = self.playwright.chromium.launch(**browser_options)

            context_options = {
                "user_agent": DEFAULT_USER_AGENT,
                "viewport": {"width": 1920, "height": 1080},
                "locale": "en-US",
            }

            self.context = self.browser.new_context(**context_options)
            self.page = self.context.new_page()
        except Exception as e:
            logger.error(e)
            self.close()
            raise
        return self

    def close(self) -> None:
        """Closes the context/browser (if launched) and stops the Playwright driver."""
        logger.info("Closing browser")
        if self.context:
            self.context.close()
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()

    def __enter__(self) -> "BrowserSession":
        """Supports `with BrowserSession() as session:` — starts the browser on entry."""
        return self.start()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Ensures the browser is closed when exiting a `with` block."""
        self.close()