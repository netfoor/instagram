"""Instagram follower/following scraper using Playwright.

Supports three authentication flows:
- Session-based: load saved cookies from a previous ``--login`` run.
- Manual: open browser, let the user log in, save the session.
- Automated: fill credentials and submit (may trigger CAPTCHA).
"""

import json
import logging
import time
from pathlib import Path
from typing import Literal

from src.utils.browser_session import BrowserSession
from src.utils.data_saver import DataSaver

logger = logging.getLogger(__name__)

UserType = Literal["following", "followers"]

BASE_URL = "https://www.instagram.com"
LOGIN_URL = "https://www.instagram.com/accounts/login/"
CHALLENGE_URLS = ("challenge", "checkpoint", "captcha", "suspicious_login")
CHALLENGE_SELECTORS = (
    'div:has-text("security code")',
    'div:has-text("Verify")',
    'div:has-text("Confirm")',
    'div:has-text("Upload a photo")',
    'div:has-text("Help us confirm")',
    'iframe[src*="captcha"]',
    'iframe[src*="challenge"]',
)

DEFAULT_SESSION_PATH = Path("data/session.json")
DEFAULT_DATA_DIR = Path("data")


class InstagramScrapper:
    """Scrapes followers and following lists from an Instagram account.

    Primary workflow::

        scrapper = InstagramScrapper(session_path="data/session.json")
        scrapper.login()              # tries session, falls back to automated
        scrapper.get_follower_list()  # saves data/followers.json
        scrapper.get_following_list() # saves data/following.json
        scrapper.get_non_followers()  # saves data/non_followers.json

    For first-time setup, use ``--login`` to authenticate manually
    and save the session for future runs.
    """

    def __init__(
        self,
        username: str = "",
        password: str = "",
        session_path: str | Path | None = None,
    ):
        self.username = username
        self.password = password
        self.session_path = Path(session_path) if session_path else None

        self.logged_in_username: str = ""
        self.is_logged_in: bool = False
        self.session: BrowserSession | None = None

    def _is_on_challenge_page(self) -> bool:
        """Check URL and page content for challenge/CAPTCHA indicators."""
        current_url = self.session.page.url

        if any(challenge in current_url for challenge in CHALLENGE_URLS):
            logger.debug("Challenge detected via URL: %s", current_url)
            return True

        for selector in CHALLENGE_SELECTORS:
            try:
                if self.session.page.locator(selector).first.is_visible(timeout=500):
                    logger.debug("Challenge detected via selector: %s", selector)
                    return True
            except Exception:
                logger.debug("Selector '%s' not found", selector)
                continue

        return False

    def _is_logged_in(self) -> bool:
        """Check for elements that only exist on authenticated pages."""
        authenticated_selectors = (
            'svg[aria-label="Home"]',
            'svg[aria-label="New post"]',
            'a[href="/accounts/edit/"]',
            'img[data-testid="user-avatar"]',
        )
        for selector in authenticated_selectors:
            try:
                if self.session.page.locator(selector).first.is_visible(timeout=500):
                    logger.debug("Authenticated element found: %s", selector)
                    return True
            except Exception:
                logger.debug("Auth element '%s' not found", selector)
                continue
        return False

    def login_with_session(self) -> bool:
        """Load a previously saved session (cookies + localStorage)."""
        if not self.session_path or not self.session_path.exists():
            logger.error("No session file at %s", self.session_path)
            return False

        try:
            self.session = BrowserSession(storage_state=self.session_path).start()
            self.session.page.goto(BASE_URL, wait_until="domcontentloaded")
            time.sleep(3)

            if self._is_logged_in():
                self.is_logged_in = True
                self.logged_in_username = self.username
                self._detect_username()
                logger.info(
                    "Session loaded successfully (user: @%s)", self.logged_in_username
                )
                return True
            else:
                logger.warning("Session expired or invalid")
                self.session.close()
                self.session = None
                return False

        except Exception as e:
            logger.error("Failed to load session: %s", e)
            if self.session:
                self.session.close()
                self.session = None
            return False

    def _detect_username(self) -> None:
        """Try to detect the logged-in username from the page."""
        if self.logged_in_username:
            return

        try:
            # Check profile link in the page
            profile_link = self.session.page.locator(
                'a[href*="/accounts/edit/"], a[href*="/accounts/"]'
            ).first
            href = profile_link.get_attribute("href", timeout=3000)
            if href and "/" in href:
                self.logged_in_username = href.strip("/").split("/")[-1]
                return
        except Exception:
            logger.debug("Could not detect username from profile link")

        try:
            # Check the URL for a username pattern
            url = self.session.page.url
            if BASE_URL in url:
                path = url.replace(BASE_URL, "").strip("/")
                if path and "/" not in path:
                    self.logged_in_username = path
        except Exception:
            logger.debug("Could not detect username from URL")

    def login_manual(self) -> bool:
        """Open browser for manual login, then save the session."""
        try:
            self.session = BrowserSession().start()
            self.session.page.goto(LOGIN_URL, wait_until="domcontentloaded")

            logger.info("=" * 60)
            logger.info("Please log in manually in the browser window.")
            logger.info("The script will wait until you reach the home page.")
            logger.info("=" * 60)

            if self.username:
                try:
                    username_input = self.session.page.locator('input[name="email"]')
                    username_input.wait_for(state="visible", timeout=5000)
                    username_input.fill(self.username)
                    logger.info("Pre-filled username: %s", self.username)
                except Exception:
                    logger.debug("Could not pre-fill username")

            self._wait_for_login(timeout=600)

            session_path = self.session.save_storage_state(DEFAULT_SESSION_PATH)
            self.is_logged_in = True
            self.logged_in_username = self.username
            logger.info("Manual login successful! Session saved to %s", session_path)
            return True

        except Exception as e:
            logger.error("Manual login failed: %s", e)
            return False
        finally:
            if self.session:
                self.session.close()
                self.session = None

    def _wait_for_login(self, timeout: int = 600) -> None:
        """Poll DOM until the login form disappears and auth elements appear."""
        deadline = time.monotonic() + timeout
        poll_interval = 2

        while time.monotonic() < deadline:
            if self._is_logged_in():
                logger.info("Login detected via authenticated page elements")
                time.sleep(2)
                return

            remaining = int(deadline - time.monotonic())
            logger.info("Waiting for login... (%ds remaining)", remaining)
            time.sleep(poll_interval)

        raise TimeoutError("Timed out waiting for manual login")

    def login(self) -> bool:
        """Try session-based login first, fall back to automated login."""
        if self.session_path and self.session_path.exists():
            logger.info("Attempting session-based login...")
            if self.login_with_session():
                return True
            logger.warning("Session login failed, trying automated login...")

        if not self.username or not self.password:
            logger.error("No credentials provided and no valid session")
            return False

        return self.login_automated()

    def login_automated(self) -> bool:
        """Automated login with username/password (may trigger CAPTCHA)."""
        try:
            self.session = BrowserSession().start()

            self.session.page.goto(LOGIN_URL, wait_until="domcontentloaded")
            time.sleep(3)

            current_url = self.session.page.url

            try:
                reject_btn = self.session.page.locator(
                    "button:has-text('Decline optional cookies')"
                )
                if reject_btn.is_visible(timeout=3000):
                    reject_btn.click()
                    logger.info("Declined cookies")
                    time.sleep(1)
            except Exception:
                logger.debug("No cookie banner found")

            if "onetap" in current_url:
                logger.info("Detected onetap login page")
                try:
                    not_you_link = (
                        self.session.page.locator("text=Not you?")
                        .or_(self.session.page.locator("text=Switch accounts"))
                        .or_(self.session.page.locator("a[href*='/accounts/login']"))
                    )

                    if not_you_link.count() > 0:
                        not_you_link.first.click()
                        time.sleep(2)
                        logger.info("Navigated to regular login page")
                    else:
                        logger.info("Forcing navigation to login page")
                        self.session.page.goto(
                            LOGIN_URL + "?force_authentication=1",
                            wait_until="domcontentloaded",
                        )
                        time.sleep(2)
                except Exception as e:
                    logger.warning("Error handling onetap page: %s", e)
                    self.session.page.goto(
                        LOGIN_URL + "?force_authentication=1",
                        wait_until="domcontentloaded",
                    )
                    time.sleep(2)

            logger.info("Filling in credentials...")
            username_input = self.session.page.locator('input[name="email"]')
            username_input.wait_for(state="visible", timeout=10000)
            username_input.fill(self.username)
            logger.info("Filled username")
            time.sleep(0.5)

            password_input = self.session.page.locator('input[name="pass"]')
            password_input.wait_for(state="visible", timeout=10000)
            password_input.fill(self.password)
            logger.info("Filled password")
            time.sleep(0.5)

            logger.info("Clicking login button...")
            login_button = (
                self.session.page.locator('div[role="button"]:has-text("Log in")')
                .or_(self.session.page.locator('button[type="submit"]'))
                .or_(self.session.page.locator('button:has-text("Log in")'))
            )
            login_button.first.click()

            logger.info("Waiting for login to complete...")
            time.sleep(5)

            current_url = self.session.page.url
            logger.info("Current URL after login: %s", current_url)

            if self._is_on_challenge_page():
                logger.warning(
                    "CAPTCHA or security challenge detected at: %s", current_url
                )
                logger.warning(
                    "Please solve the challenge in the browser window. "
                    "Waiting up to 5 minutes..."
                )
                self._wait_for_challenge_resolution(timeout=300)
                current_url = self.session.page.url
                logger.info("URL after challenge resolution: %s", current_url)

            try:
                not_now_btn = self.session.page.locator("button:has-text('Not now')")
                if not_now_btn.is_visible(timeout=3000):
                    not_now_btn.click()
                    logger.info("Clicked 'Not now' on save login dialog")
                    time.sleep(2)
            except Exception:
                logger.debug("No save login dialog found")

            try:
                not_now_btn = self.session.page.locator("button:has-text('Not Now')")
                if not_now_btn.is_visible(timeout=3000):
                    not_now_btn.click()
                    logger.info("Clicked 'Not Now' on notifications dialog")
                    time.sleep(2)
            except Exception:
                logger.debug("No notifications dialog found")

            time.sleep(3)

            is_on_challenge = self._is_on_challenge_page()

            if is_on_challenge:
                logger.warning(
                    "CAPTCHA detected after redirect. "
                    "Please solve the challenge in the browser. Waiting up to 5 minutes..."
                )
                self._wait_for_challenge_resolution(timeout=300)
                is_on_challenge = self._is_on_challenge_page()

            if is_on_challenge:
                logger.error(
                    "Login failed - still on challenge page after intervention"
                )
                return False

            if self._is_logged_in():
                self.is_logged_in = True
                self.logged_in_username = self.username
                logger.info("Login successful!")
                self.session.save_storage_state(DEFAULT_SESSION_PATH)
                return True

            logger.error("Login failed - could not detect authenticated page")
            return False

        except Exception as e:
            logger.error("Login failed: %s", e)
            if self.session:
                self.session.close()
                self.session = None
            return False

    def _wait_for_challenge_resolution(self, timeout: int = 300) -> None:
        """Poll until the challenge page is gone or timeout expires."""
        deadline = time.monotonic() + timeout
        poll_interval = 5

        while time.monotonic() < deadline:
            current_url = self.session.page.url
            if not self._is_on_challenge_page():
                logger.info("Challenge resolved at: %s", current_url)
                return

            remaining = int(deadline - time.monotonic())
            logger.info(
                "Still on challenge page (%ds remaining): %s",
                remaining,
                current_url,
            )
            time.sleep(poll_interval)

        logger.error("Timed out waiting for challenge resolution")

    def go_to_profile(self) -> bool:
        """Navigate to the logged-in user's profile page.

        Returns True if the profile loaded, False otherwise.
        """
        if not self.is_logged_in or not self.session:
            logger.error("Not logged in")
            return False

        try:
            target_username = self.logged_in_username

            if not target_username:
                logger.error("No username available")
                return False

            url = f"{BASE_URL}/{target_username}/"

            self.session.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            # Wait for profile content to render (SPA)
            try:
                self.session.page.locator(
                    'header section, [data-testid="user-avatar"]'
                ).first.wait_for(state="visible", timeout=10000)
            except Exception:
                logger.debug("Profile header not found, proceeding anyway")

            logger.info("Profile page loaded: %s", self.session.page.url)
            return True

        except Exception as e:
            logger.error("Error loading profile: %s", e)
            return False

    def get_following_list(self):
        """Scrape the accounts you follow and save to data/following.json."""
        data = self._get_user_list(list_type="following")
        saver = DataSaver(data=data, filename="following", output_dir=Path("data"))
        saver.save_json()

    def get_follower_list(self):
        """Scrape your followers and save to data/followers.json."""
        data = self._get_user_list(list_type="followers")
        saver = DataSaver(data=data, filename="followers", output_dir=DEFAULT_DATA_DIR)
        saver.save_json()

    def get_non_followers(self) -> list[dict]:
        """Compare followers and following lists, return users you follow who don't follow you back."""
        followers_path = DEFAULT_DATA_DIR / "followers.json"
        following_path = DEFAULT_DATA_DIR / "following.json"

        if not followers_path.exists():
            logger.error("No followers.json found at %s", followers_path)
            return []
        if not following_path.exists():
            logger.error("No following.json found at %s", following_path)
            return []

        with open(followers_path, encoding="utf-8") as f:
            followers = json.load(f)
        with open(following_path, encoding="utf-8") as f:
            following = json.load(f)

        follower_usernames = {u["username"] for u in followers}
        non_followers = [
            u for u in following if u["username"] not in follower_usernames
        ]

        logger.info(
            "Comparison: %d following, %d followers, %d don't follow you back",
            len(following),
            len(followers),
            len(non_followers),
        )

        saver = DataSaver(
            data=non_followers, filename="non_followers", output_dir=DEFAULT_DATA_DIR
        )
        saver.save_json()

        return non_followers

    def _get_user_list(self, list_type: UserType) -> list[dict]:
        """Open the followers/following dialog, scroll to load all users, and collect them.

        Args:
            list_type: Either ``"followers"`` or ``"following"``.

        Returns:
            List of dicts with ``username``, ``full_name``, and ``profile_url``.
        """
        try:
            if not self.go_to_profile():
                return []

            logger.info("Opening %s list...", list_type)

            # Try multiple selectors for the followers/following link
            link_selectors = [
                f'a[href*="/{list_type}/"]',
                f'span:has-text("{list_type}") >> xpath=ancestor::a',
                f'a:has-text("{list_type}")',
                f'button:has-text("{list_type}")',
            ]

            link = None
            for selector in link_selectors:
                try:
                    candidate = self.session.page.locator(selector).first
                    candidate.wait_for(state="visible", timeout=5000)
                    link = candidate
                    logger.info("Found %s link with selector: %s", list_type, selector)
                    break
                except Exception:
                    logger.debug("Selector '%s' not found", selector)
                    continue

            if not link:
                logger.error(
                    "Could not find %s link on profile page. Page URL: %s",
                    list_type,
                    self.session.page.url,
                )
                return []

            link.click()
            time.sleep(3)

            logger.info("Waiting for user list dialog...")
            dialog = self.session.page.locator('div[role="dialog"]').first
            dialog.wait_for(state="visible", timeout=10000)

            users: list[dict] = []
            seen_usernames: set[str] = set()
            previous_count = 0
            no_change_count = 0

            logger.info("Scrolling and collecting %s...", list_type)

            scroll_pause_time = 1.5
            max_no_change = 5

            while True:
                user_links = dialog.locator('a[role="link"]').all()

                for link_elem in user_links:
                    try:
                        href = link_elem.get_attribute("href")
                        if not href or href == "#" or not href.startswith("/"):
                            continue

                        username = href.strip("/").split("/")[-1]

                        if username in seen_usernames:
                            continue

                        try:
                            link_text = link_elem.inner_text()
                            full_name = link_text if link_text else ""
                        except Exception:
                            full_name = ""

                        user_data = {
                            "username": username,
                            "full_name": full_name,
                            "profile_url": f"{BASE_URL}/{username}/",
                        }

                        seen_usernames.add(username)
                        users.append(user_data)
                        logger.info("  [%d] @%s", len(users), username)

                    except Exception as e:
                        logger.debug("Error extracting user: %s", e)
                        continue

                current_count = len(users)
                if current_count == previous_count:
                    no_change_count += 1
                    logger.info(
                        "No new users found (attempt %d/%d) - Total: %d",
                        no_change_count,
                        max_no_change,
                        current_count,
                    )

                    if no_change_count >= max_no_change:
                        logger.info("No more users to load - scraping complete")
                        break
                else:
                    if current_count > previous_count:
                        new_users = current_count - previous_count
                        logger.info(
                            "Found %d new users! Total: %d", new_users, current_count
                        )
                    no_change_count = 0
                    previous_count = current_count

                logger.info("Scrolling to load more...")
                try:
                    scrollable = (
                        dialog.locator("div")
                        .filter(has=dialog.locator('a[role="link"]'))
                        .first
                    )
                    scrollable.evaluate("el => el.scrollTop = el.scrollHeight")
                except Exception:
                    try:
                        dialog.evaluate("el => el.scrollTop = el.scrollHeight")
                    except Exception:
                        dialog.evaluate("el => el.scrollBy(0, 1000)")

                time.sleep(scroll_pause_time)

            logger.info("Collected %d %s", len(users), list_type)
            return users

        except Exception as e:
            logger.error("Error getting %s list: %s", list_type, e)
            return []
