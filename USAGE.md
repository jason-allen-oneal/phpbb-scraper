# Quick Start Guide

See [README.md](README.md) for full documentation.

## First Run

1. Configure `.env` with your forum URL (copy from `.env.example`)
2. Run with browser visible to log in:
```bash
python main.py --task members --start 1 --stop 1 --show-browser --force-login
```
3. Log in manually when prompted
4. Session is saved automatically for future runs

## Subsequent Runs

Run headlessly after authentication:

```bash
# Scrape members
python main.py --task members --start 1 --stop 100

# Scrape forums
python main.py --task forums --limit-pages 5

# Scrape specific thread
python main.py --task thread --url "https://forum.example.com/viewtopic.php?t=12345"

# Scrape everything
python main.py --task all --start 1 --stop 1000
```

## Common Options

- `--show-browser` - Show browser window (for debugging or login)
- `--force-login` - Force fresh login
- `--delay SECONDS` - Delay between requests (default: 1.0)
- `--limit-pages N` - Limit pages per forum

## Storage

Configure in `.env`:
- `OUTPUT_MODE=file` - Save to JSON files (default)
- `OUTPUT_MODE=db` - Save to MySQL database

## Session Management

- Session saved to `session.json` automatically
- Reused on subsequent runs
- Use `--force-login` if session expires
