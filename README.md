# Instagram Scraper

Automate Instagram data extraction with Playwright. Log in (manually or via saved session), scrape followers and following lists, and find out who doesn't follow you back.

## Features

- **Follower & following scraper** — Auto-scrolls the dialog to load every user, saves username, full name, and profile URL as JSON.
- **Non-follower detection** — Compares followers vs. following lists and identifies users you follow who don't follow you back.
- **Session-based auth** — Save your login session once (`--login`) and reuse it across runs, avoiding repeated CAPTCHAs.
- **Automated login** — Fills credentials and submits. Handles cookie banners, onetap pages, and CAPTCHA challenges.
- **Manual login** — Opens a browser window for you to log in yourself. Session is saved automatically.

## Prerequisites

- [Python 3.12+](https://www.python.org/downloads/)
- [uv](https://github.com/astral-sh/uv) (package manager)

## Installation

```bash
# Clone the repository
git clone git@github.com:netfoor/instagram.git
cd instagram

# Install dependencies
uv sync

# Install Playwright Chromium + system dependencies
uv run playwright install --with-deps chromium

# Create your environment file
cp .env.example .env
```

Then edit `.env` with your Instagram credentials:

```
IG_USERNAME=your_username
IG_PASSWORD=your_password
```

## Usage

### First-time login

Opens a visible browser window. Log in manually — the script waits until you reach the home page and saves the session to `data/session.json`.

```bash
uv run python main.py --login
```

### Scrape followers & following

Uses the saved session (or falls back to automated login with your credentials).

```bash
uv run python main.py
```

Saves:
- `data/followers.json`
- `data/following.json`

### Find non-followers

Compares the two lists and shows who doesn't follow you back.

```bash
uv run python main.py --compare
```

Saves: `data/non_followers.json`

### CLI Options

| Flag | Description |
|---|---|
| `--login` | Open browser for manual login and save session |
| `--compare` | Compare followers/following and show non-followers |
| `--username` | Override `IG_USERNAME` env var |
| `--password` | Override `IG_PASSWORD` env var |

## Project Structure

```
instagram/
├── main.py                          # CLI entry point
├── src/
│   ├── scrappers/
│   │   └── instagram_scrapper.py    # Core scraper logic
│   └── utils/
│       ├── browser_session.py        # Playwright browser lifecycle
│       └── data_saver.py            # JSON file writer
├── tests/
│   └── test_browser_session.py      # Unit tests
├── data/                            # Output directory (git-ignored)
│   ├── session.json
│   ├── followers.json
│   ├── following.json
│   └── non_followers.json
└── pyproject.toml                   # Project config + tool settings
```

## Development

### Running tests

```bash
# Unit tests (no browser required)
uv run pytest -m "not integration" -v

# Integration tests (requires Chromium)
uv run pytest -m integration -v
```

### Linting & formatting

```bash
# Check for lint errors
uv run ruff check .

# Auto-fix formatting
uv run ruff format .

# Type checking
uv run mypy src/
```

All checks must pass before committing:

```bash
uv run ruff check . && uv run ruff format --check . && uv run mypy src/ && uv run pytest -m "not integration" -v
```

## How It Works

1. **Authentication** — Tries session-based login first (loads `data/session.json`). If expired or missing, falls back to automated login with credentials from `--username`/`--password` or the `.env` file.

2. **Scraping** — Navigates to your profile, opens the followers/following dialog, and scrolls repeatedly until no new users load for 5 consecutive cycles. Each user is extracted as `{username, full_name, profile_url}`.

3. **Comparison** — Builds a set of follower usernames, filters the following list against it, and outputs the difference.

## License

MIT
