import argparse
import logging
import os

from dotenv import load_dotenv

from src.scrappers.instagram_scrapper import InstagramScrapper

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s"
)


def main():
    parser = argparse.ArgumentParser(description="Instagram follower/following scraper")
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for manual login and save session to data/session.json",
    )
    parser.add_argument(
        "--username",
        type=str,
        default=None,
        help="Instagram username (overrides IG_USERNAME env var)",
    )
    parser.add_argument(
        "--password",
        type=str,
        default=None,
        help="Instagram password (overrides IG_PASSWORD env var)",
    )
    args = parser.parse_args()

    load_dotenv()

    username = args.username or os.environ.get("IG_USERNAME", "")
    password = args.password or os.environ.get("IG_PASSWORD", "")

    scrapper = InstagramScrapper(
        username=username,
        password=password,
        session_path="data/session.json",
    )

    if args.login:
        success = scrapper.login_manual()
        if not success:
            raise SystemExit(1)
        return

    success = scrapper.login()
    if not success:
        raise SystemExit(
            "Login failed. Run with --login to authenticate manually first."
        )

    scrapper.get_follower_list()
    scrapper.get_following_list()


if __name__ == "__main__":
    main()
