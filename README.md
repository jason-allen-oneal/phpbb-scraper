# phpBB Forum Scraper

A robust Python-based scraper for phpBB forums with Playwright automation to handle Cloudflare protection and session management.

## Features

- **Playwright Browser Automation**: Bypasses Cloudflare challenges automatically
- **Session Management**: Persistent login with cookie storage
- **Flexible Storage**: Save to files (JSON Lines) or MySQL database
- **Multiple Scraping Modes**:
  - Member profiles (UID enumeration)
  - Forum structure and topics
  - Thread posts with pagination
  - Complete scraping (all of the above)
- **Cloudflare Protection**: Uses real browser automation to handle anti-bot measures

## Installation

1. Clone this repository:
```bash
git clone https://github.com/jason-allen-oneal/phpbb-scraper.git
cd phpbb-scraper
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Install Playwright browsers:
```bash
playwright install chromium
```

4. Configure your environment:
```bash
cp .env.example .env
# Edit .env with your forum URL and settings
```

## Configuration

Edit `.env` file with your settings:

```env
# Required
BASE_URL=https://your-forum.com/

# Optional
USER_AGENT=Mozilla/5.0...
OUTPUT_MODE=file  # or 'db' for database
OUTPUT_DIR=output
```

For database storage, also configure:
```env
OUTPUT_MODE=db
DB_TYPE=mysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=your_user
DB_PASS=your_password
DB_NAME=phpbb_scraper
```

## Usage

### Application Flow

The scraper follows this flow:
1. **Starts Playwright browser** (headless by default)
2. **Loads saved session** (from `session.json` if exists)
3. **Checks login status** by visiting the forum index
4. **Performs login if needed** (waits for user to complete login in browser)
5. **Saves session** (cookies and storage state)
6. **Executes the selected task** using the authenticated session
7. **Stores results** (to files or database as configured)

### First Run - Interactive Login

For the first run, use `--show-browser` and `--force-login` to complete authentication:

```bash
python main.py --task members --start 1 --stop 1 --show-browser --force-login
```

This will:
- Open a browser window
- Navigate to the login page
- Wait for you to log in manually
- Save the session for future use
- Proceed with the scraping task

### Subsequent Runs

Once authenticated, you can run headlessly:

```bash
# Scrape member profiles (UID 1-100)
python main.py --task members --start 1 --stop 100

# Scrape all forums and topics
python main.py --task forums --limit-pages 10

# Scrape a specific thread
python main.py --task thread --url "https://forum.example.com/viewtopic.php?t=12345"

# Scrape everything
python main.py --task all --start 1 --stop 1000
```

### Command Line Options

```
--task {thread,members,forums,all}
    Which scrape to run
    
--url URL
    Topic URL (required when task=thread)
    
--delay DELAY
    Delay between requests (default: 1.0 seconds)
    
--start START
    Starting UID or page offset (default: 1)
    
--stop STOP
    Stop UID or page offset
    
--step STEP
    Pagination step for thread scraping (default: 10)
    
--limit-pages LIMIT_PAGES
    Limit forum pages per forum
    
--show-browser
    Run Playwright in headed mode (shows browser window)
    
--force-login
    Force a fresh login even if session exists
```

## Architecture

### Project Structure

```
phpbb-scraper/
├── lib/                    # Core library modules
│   ├── __init__.py
│   ├── db.py              # Database operations
│   ├── forum.py           # Forum discovery and scraping
│   ├── members.py         # Member profile scraping
│   ├── session_manager.py # Browser/session management
│   ├── storage.py         # Storage abstraction
│   └── topic.py           # Thread/post scraping
├── main.py                # Entry point
├── config.py              # Configuration loader
├── requirements.txt       # Python dependencies
├── .env.example          # Example environment config
└── README.md             # This file
```

### Key Components

#### SessionManager (`lib/session_manager.py`)
- Manages Playwright browser lifecycle
- Handles login detection and authentication
- Deals with Cloudflare challenges automatically
- Persists cookies and session state

#### Storage (`lib/storage.py`)
- Abstract storage layer
- Supports file-based (JSONL) or database storage
- Automatic fallback from database to file on errors

#### Scrapers
- **members.py**: Profile scraping with UID enumeration
- **topic.py**: Thread content extraction with pagination
- **forum.py**: Forum discovery and topic listing

## Cloudflare Mitigation

This scraper uses Playwright with real browser automation to bypass Cloudflare:

1. Uses Chromium with stealth arguments
2. Real browser fingerprint (not automated detection)
3. Automatic challenge detection and waiting
4. Persistent sessions to reduce challenges

## Output

### File Mode (default)
Data is saved as JSON Lines (`.jsonl`) files in the `output/` directory:
- `output/members.jsonl` - Member profiles
- `output/forum_topics.jsonl` - Topics
- `output/thread_posts.jsonl` - Posts
- `output/members/{uid}_{username}.json` - Individual member backups

### Database Mode
When `OUTPUT_MODE=db`, data is stored in MySQL tables:
- `members` - User profiles
- `forum_topics` - Forum topics
- `thread_posts` - Individual posts
- `scraped_data` - Generic collections

## Troubleshooting

### Playwright installation fails
```bash
# Install with dependencies
playwright install chromium --with-deps
```

### Cloudflare challenges not resolving
- Ensure you're using `--show-browser` on first run
- Check that you're not rate-limiting (increase `--delay`)
- Clear `session.json` and re-authenticate

### Session expires
```bash
# Force a fresh login
python main.py --task members --start 1 --stop 1 --show-browser --force-login
```

### Database connection errors
- Verify database credentials in `.env`
- Ensure MySQL server is running
- Check that database exists and user has proper permissions

## Contributing

Contributions are welcome! Please ensure:
- Code follows existing style and structure
- All logic remains in `lib/` modules
- Main entry point stays minimal

## License

See LICENSE file for details.
