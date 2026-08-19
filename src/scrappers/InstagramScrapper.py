import logging
from src.utils.BrowserSession import BrowserSession
import time
from typing import Literal
from src.utils.DataSaver import DataSaver
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

UserType = Literal["following", "followers"]

BASE_URL = "https://www.instagram.com"
LOGIN_URL = "https://www.instagram.com/accounts/login/"

class InstagramScrapper:

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

        self.logged_in_username: str = ""
        self.is_logged_in: bool = False
        self.session: BrowserSession = None
    
    def login(self):
        try: 
            with BrowserSession() as session:
                session.page.goto(LOGIN_URL, wait_until="domcontentloaded")
                time.sleep(3)
                
                current_url = session.page.url

                try:
                    reject_btn = session.page.locator(("button:has-text('Decline optional cookies')"))
                    if reject_btn.is_visible(timeout=3000):
                        reject_btn.click()
                        logger.info("Declined cookies")
                        time.sleep(1)
                except:
                    pass

                if "onetap" in current_url: 
                    logger.info("Detected onetap login page")
                    try: 
                        not_you_link = session.page.locator("text=Not you?").or_(
                            session.page.locator("text=Switch accounts")
                        ).or_(
                            session.page.locator("a[href*='/accounts/login']")
                        )
                        
                        if not_you_link.count() > 0:
                            not_you_link.first.click()
                            time.sleep(2)
                            logger.info("Navigated to regular login page")
                        else:
                            # If can't find the link, force navigate to login
                            logger.info("Forcing navigation to login page")
                            session.page.goto(LOGIN_URL + "?force_authentication=1", wait_until="domcontentloaded")
                            time.sleep(2)
                    except Exception as e:
                        logger.warning(e)
                        session.page.goto(LOGIN_URL + "?force_authentication=1", wait_until="domcontentloaded")
                        time.sleep(2)
                logger.info("Filling in credentials...")
                username_input = session.page.locator('input[name="email"]')
                username_input.wait_for(state="visible", timeout=10000)
                username_input.fill(self.username)
                logger.info(f"Filled username")
                time.sleep(0.5)
                
                # Fill in password
                password_input = session.page.locator('input[name="pass"]')
                password_input.wait_for(state="visible", timeout=10000)
                password_input.fill(self.password)
                logger.info("Filled password")
                time.sleep(0.5)

                logger.info("Clicking login button...")
                # Instagram uses div[role="button"] instead of real button
                login_button = session.page.locator('div[role="button"]:has-text("Log in")').or_(
                    session.page.locator('button[type="submit"]')
                ).or_(
                    session.page.locator('button:has-text("Log in")')
                )
                login_button.first.click()
                
                logger.info("Waiting for login to complete...")
                
                # Wait for navigation after login
                # Instagram may redirect to home page or ask to save login info
                time.sleep(5)
                
                # Check if "Save Your Login Info?" dialog appears
                try:
                    not_now_btn = session.page.locator("button:has-text('Not now')")
                    if not_now_btn.is_visible(timeout=3000):
                        not_now_btn.click()
                        logger.info("Clicked 'Not now' on save login dialog")
                        time.sleep(2)
                except:
                    pass
                
                # Check if "Turn on Notifications?" dialog appears
                try:
                    not_now_btn = session.page.locator("button:has-text('Not Now')")
                    if not_now_btn.is_visible(timeout=3000):
                        not_now_btn.click()
                        logger.info("Clicked 'Not Now' on notifications dialog")
                        time.sleep(2)
                except:
                    pass


                current_url = session.page.url
                if "login" not in current_url:
                    self.is_logged_in = True
                    self.logged_in_username = username  # Store the username
                    self.session = session
                    logger.info("Login successful!")
                    return True
                else:
                    logger.error("Login failed - still on login page")
                    return False
        except Exception as e:
            logging.warning(e)
        
    


    def go_to_profile(self):
        if not self.is_logged_in:
            logger.error("Not loggin in")
            return False
        
        try: 
            target_username = self.logged_in_username

            if not target_username:
                logger.error("Not username provided and not loggin in")
            
            url = f"{BASE_URL/{target_username}}/"

            self.session.page.goto(url, wait_until="domcontentloaded", timeout=15000)
            time.sleep(3)

            logger.info("Profile page loaded")
            return True

        except Exception as e:
            logger.error(e)
            return False

    def get_following_list(self):
        data = self._get_user_list(list_type="following")
        saver = DataSaver(data=data, filename='following', output_dir=Path("data"))
        saver.save_json()
        

    def get_follower_list(self):
        data = self._get_user_list(list_type="followers")
        saver = DataSaver(data=data, filename='followers', output_dir=Path("data"))
        saver.save_json()
        

    def _get_user_list(self, list_type: UserType):
        max_users = None #Alld
        try:
            profile = self.go_to_profile()

            if profile:
                logger.info(f"Opening {list_type} list...")
                # Use the href selector which we found works
                link_selector = f'a[href*="/{list_type}/"]'
                link = self.session.page.locator(link_selector).first
                link.wait_for(state="visible", timeout=10000)
                link.click()
                time.sleep(3)
                
                # Wait for the modal/dialog to appear
                logger.info("Waiting for user list dialog...")
                dialog = self.session.page.locator('div[role="dialog"]').first
                dialog.wait_for(state="visible", timeout=10000)
                
                # Scroll and collect users
                users = []
                previous_count = 0
                no_change_count = 0
                
                logger.info(f"Scrolling and collecting {list_type}...")
                
                scroll_pause_time = 1.5  # Time to wait for new content to load
                max_no_change = 5  # Increase patience - sometimes Instagram is slow

                while True:
                    # Get all user links in the dialog
                    user_links = dialog.locator('a[role="link"]').all()
                    
                    # Extract user info 
                    for link_elem in user_links:
                        try:
                            href = link_elem.get_attribute('href')
                            if not href or href == '#' or not href.startswith('/'):
                                continue
                            
                            # Extract username from href (e.g., /username/ -> username)
                            username = href.strip('/').split('/')[-1]
                            
                            # Skip if already collected
                            if any(u['username'] == username for u in users):
                                continue
                            
                            # Try to get full name from the link text or nearby span
                            try:
                                link_text = link_elem.inner_text()
                                full_name = link_text if link_text else ""
                            except:
                                full_name = ""
                            
                            user_data = {
                                'username': username,
                                'full_name': full_name,
                                'profile_url': f"{self.BASE_URL}/{username}/"
                            }
                            
                            users.append(user_data)
                            logger.info(f"  [{len(users)}] @{username}")

                            if max_users and len(users) >= max_users:
                                logger.info(f"Reached max_users limit: {max_users}")
                                return users
                                
                        except Exception as e:
                            logger.debug(f"Error extracting user: {e}")
                            continue
                    # Check if new users were found
                    current_count = len(users)
                    if current_count == previous_count:
                        no_change_count += 1
                        logger.info(f"No new users found (attempt {no_change_count}/{max_no_change}) - Total: {current_count}")
                        
                        # If no new users after several scrolls, we're done
                        if no_change_count >= max_no_change:
                            logger.info("No more users to load - scraping complete")
                            break
                    else:
                        # Progress! Reset counter
                        if current_count > previous_count:
                            new_users = current_count - previous_count
                            logger.info(f"Found {new_users} new users! Total: {current_count}")
                        no_change_count = 0
                        previous_count = current_count
                    
                    # Scroll the dialog to load more users
                    # Instagram loads more as you scroll down
                    logger.info(f"⬇Scrolling to load more...")
                    try:
                        # Method 1: Scroll to bottom of the scrollable container
                        # The dialog has a scrollable div inside it
                        scrollable = dialog.locator('div').filter(has=dialog.locator('a[role="link"]')).first
                        scrollable.evaluate("el => el.scrollTop = el.scrollHeight")
                    except:
                        try:
                            # Method 2: Fallback - scroll the dialog itself
                            dialog.evaluate("el => el.scrollTop = el.scrollHeight")
                        except:
                            # Method 3: Last resort - scroll by a large amount
                            dialog.evaluate("el => el.scrollBy(0, 1000)")
                    
                    # Wait for Instagram to load more content
                    time.sleep(scroll_pause_time)
                
                logger.info(f"Collected {len(users)} {list_type}")
                return users

        except Exception as e:
            logger.error(f"Error getting {list_type} list: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return []                    


                