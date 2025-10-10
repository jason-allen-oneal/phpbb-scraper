# 403 Error Handling

## Overview

This scraper includes automatic cookie refresh functionality to handle 403 (Forbidden) errors from Cloudflare or other anti-bot measures.

## How It Works

When the scraper encounters a 403 error during any request (member profiles, topics, forums), it will:

1. **Detect the 403**: All fetch functions monitor for HTTP 403 responses
2. **Attempt Cookie Refresh**: Uses `cloudscraper` to bypass Cloudflare challenges and obtain fresh cookies
3. **Retry Request**: Automatically retries the failed request once with the new cookies
4. **Persist Cookies**: Updates the `DF_COOKIES` in your `.env` file with the refreshed cookies
5. **Prevent Infinite Loops**: Only attempts refresh once per request to avoid infinite retry loops

## Affected Modules

- `member.py` - Profile scraping (`fetch_profile_html()`)
- `topic.py` - Topic scraping (`fetch_page()`)
- `forum.py` - Forum scraping (`fetch()`)

## Requirements

The automatic cookie refresh requires `cloudscraper` to be installed (included in `requirements.txt`).

## Example Output

When a 403 is encountered, you'll see output like:
```
[!] UID 220 → HTTP 403, attempting to refresh cookies...
[+] Cookies refreshed, retrying UID 220
[+] UID 220 → Parsed username_example
```

If cookie refresh fails:
```
[!] UID 220 → HTTP 403, attempting to refresh cookies...
[-] Failed to refresh cookies for UID 220
[-] UID 220 → HTTP 403
```

## Configuration

You can configure the cookie refresh behavior through environment variables in `.env`:

- `HTTP_TIMEOUT`: Timeout for cloudscraper requests (default: 30 seconds)
- `DF_COOKIES`: Your authentication cookies (automatically updated by the scraper)
- `SESSION_REFRESH_URL`: URL to use for cookie refresh (defaults to the failed URL)

## Troubleshooting

If you continue to get 403 errors even after automatic refresh:

1. Ensure `cloudscraper` is installed: `pip install cloudscraper`
2. Check that your `DF_COOKIES` in `.env` are still valid
3. Try manually refreshing your cookies in the browser and updating `.env`
4. Check if the target site has implemented additional anti-bot measures
5. Increase delays between requests with the `--delay` parameter

## Manual Cookie Refresh

If automatic refresh isn't working, you can manually update cookies:

1. Open your browser's DevTools (F12)
2. Go to the Application/Storage tab
3. Copy all relevant cookies (phpbb_*, cf_clearance, PHPSESSID, etc.)
4. Update `DF_COOKIES` in your `.env` file:
   ```
   DF_COOKIES='cookie1=value1; cookie2=value2; ...'
   ```
5. Restart the scraper
