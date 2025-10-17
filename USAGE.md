# DarkForum Scraper Usage Guide

## Quick Start

### 1. Authenticate (first run)
The first scraping run will launch Playwright. Use the `--show-browser` flag to see the browser window and `--force-login` to
force a fresh login if needed:

```bash
# Trigger an interactive login (opens a browser window)
python main.py --task members --start 1 --stop 1 --show-browser --force-login
```

Once authenticated, subsequent runs can stay headless unless the session expires.

### 2. Run Scraper

```bash
# Scrape everything (members + forums + thread content)
python main.py --task all --start 1 --stop 100

# Scrape only members
python main.py --task members --start 1 --stop 1000

# Scrape only forums
python main.py --task forums --limit-pages 5

# Scrape specific thread
python main.py --task thread --url "https://www.darkforum.com/viewtopic.php?t=12345"
```

## Configuration

The scraper uses environment variables from `.env`:

```env
# Authentication
DF_COOKIES='your_cookies_here'
USER_AGENT=Mozilla/5.0...
BASE_URL=https://www.darkforum.com/

# Storage
OUTPUT_MODE=db  # or 'file'
DB_TYPE=mysql
DB_HOST=localhost
DB_USER=jason
DB_PASS=your_password
DB_NAME=darkforum
```

## Database Setup

The scraper automatically creates the necessary database tables. Make sure your MySQL database exists and the user has proper permissions.

## Features

- **Session Management**: Automatic login and cookie handling
- **Cloudflare Bypass**: Uses Playwright to handle challenges
- **Database Storage**: Stores all data in MySQL
- **Resume Capability**: Can resume from where it left off
- **Error Handling**: Robust error handling and retry logic

## Output

All scraped data is stored in the MySQL database:
- `members` - User profiles
- `forum_topics` - Forum topics
- `thread_posts` - Individual posts
- `scraped_data` - Other collections
