"""
Tests for BrowserSession.

Run:
    pytest -m "not integration" -v   # fast, mocked, no browser needed
    pytest -m integration -v         # requires `playwright install chromium`
    pytest -v                        # everything
"""

from unittest.mock import MagicMock, patch

import pytest

from src.utils.browser_session import DEFAULT_USER_AGENT, BrowserSession


def browser_session_mock_playwright_chain():
    """
    Builds a fake object graph mimicking:
        sync_playwright().start().chromium.launch().new_context().new_page()

    Returns each link so tests can assert on how it was called.
    """
    mock_page = MagicMock(name="page")
    mock_context = MagicMock(name="context")
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock(name="browser")
    mock_browser.new_context.return_value = mock_context

    mock_playwright = MagicMock(name="playwright")
    mock_playwright.chromium.launch.return_value = mock_browser

    mock_sync_playwright_cm = MagicMock(name="sync_playwright()")
    mock_sync_playwright_cm.start.return_value = mock_playwright

    return (
        mock_sync_playwright_cm,
        mock_playwright,
        mock_browser,
        mock_context,
        mock_page,
    )


class TestStart:
    @patch("src.utils.browser_session.sync_playwright")
    def test_headless_flag_is_forwarded(self, mock_sync_playwright):
        cm, pw, _browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        session = BrowserSession(headless=True).start()

        launch_kwargs = pw.chromium.launch.call_args.kwargs
        assert launch_kwargs["headless"] is True
        assert session.browser is _browser

    @patch("src.utils.browser_session.sync_playwright")
    def test_anti_automation_arg_always_present(self, mock_sync_playwright):
        cm, pw, _browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        BrowserSession().start()

        launch_kwargs = pw.chromium.launch.call_args.kwargs
        assert "--disable-blink-features=AutomationControlled" in launch_kwargs["args"]

    @patch("src.utils.browser_session.sync_playwright")
    def test_extra_launch_kwargs_are_merged_in(self, mock_sync_playwright):
        cm, pw, _browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        BrowserSession(slow_mo=50).start()

        launch_kwargs = pw.chromium.launch.call_args.kwargs
        assert launch_kwargs["slow_mo"] == 50

    @patch("src.utils.browser_session.sync_playwright")
    def test_context_uses_expected_fingerprint(self, mock_sync_playwright):
        cm, _pw, browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        BrowserSession().start()

        context_kwargs = browser.new_context.call_args.kwargs
        assert context_kwargs["user_agent"] == DEFAULT_USER_AGENT
        assert context_kwargs["viewport"] == {"width": 1920, "height": 1080}
        assert context_kwargs["locale"] == "en-US"

    @patch("src.utils.browser_session.sync_playwright")
    def test_page_is_created_from_context(self, mock_sync_playwright):
        cm, _pw, _browser, context, page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        session = BrowserSession().start()

        context.new_page.assert_called_once()
        assert session.page is page


class TestClose:
    def test_close_before_start_does_not_raise(self):
        # playwright/browser are still None if start() never ran
        BrowserSession().close()

    @patch("src.utils.browser_session.sync_playwright")
    def test_close_stops_browser_then_playwright(self, mock_sync_playwright):
        cm, pw, browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        session = BrowserSession().start()
        session.close()

        browser.close.assert_called_once()
        pw.stop.assert_called_once()


class TestContextManager:
    @patch("src.utils.browser_session.sync_playwright")
    def test_enter_returns_started_session(self, mock_sync_playwright):
        cm, _pw, _browser, _context, page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        with BrowserSession() as session:
            assert session.page is page

    @patch("src.utils.browser_session.sync_playwright")
    def test_exit_closes_even_if_body_raises(self, mock_sync_playwright):
        cm, _pw, browser, _context, _page = browser_session_mock_playwright_chain()
        mock_sync_playwright.return_value = cm

        with pytest.raises(ValueError), BrowserSession():
            raise ValueError("boom")

        browser.close.assert_called_once()
        cm.start.return_value.stop.assert_called_once()


@pytest.mark.integration
class TestRealBrowser:
    """Slow tests that launch an actual browser. Requires `playwright install --with-deps chromium`."""

    def test_can_load_a_real_page(self):
        with BrowserSession(headless=True) as session:
            session.page.goto("https://example.com")
            assert "Example Domain" in session.page.title()
