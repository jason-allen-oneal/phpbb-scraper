# Application Flow Documentation

This document details the exact flow of the phpBB scraper, ensuring the implementation matches requirements.

## Requirements

From the issue:
> The user runs it, a window opens, the user logs in or is detected as logged in, cookies and/or session data is collected for future requests, then the selected task is run.

## Implementation Flow

### 1. User Execution
```bash
python main.py --task members --start 1 --stop 10 --show-browser
```

### 2. Entry Point (`main.py`)
- `main()` function is called
- Initializes storage system (`init_storage()`)
- Calls `asyncio.run(dispatch(args))`

### 3. Session Manager Initialization (`dispatch()`)
```python
async with SessionManager(headless=not args.show_browser) as session:
```

When entering the context manager (`__aenter__`):

#### 3a. Start Playwright Session
```python
await self.start_session(headless=self.headless)
```

**Actions:**
1. Starts Playwright with `async_playwright().start()`
2. Launches Chromium browser with anti-detection arguments:
   - `--disable-blink-features=AutomationControlled` (hide automation)
   - `--no-sandbox` (for running in containers)
3. Creates browser context with:
   - Custom User-Agent
   - Standard viewport (1366x768)
   - US locale and timezone
   - Custom HTTP headers

#### 3b. Load Saved Session
```python
await self._load_session_state()
```

**Actions:**
1. Checks if `session.json` exists
2. If exists, loads cookies from file
3. Adds cookies to browser context
4. Restores previous session state

**Result:** User is potentially already logged in from previous run

#### 3c. Open New Page
```python
self.page = await self.context.new_page()
```

A new browser page/tab is created for navigation.

### 4. Login Check and Authentication
```python
await session.ensure_logged_in(force_login=args.force_login)
```

#### 4a. Check Login Status
```python
if not force_login and await self._looks_logged_in():
    return True
```

**Actions:**
1. Navigates to forum index page
2. Waits 2 seconds for page load
3. Searches for indicators of logged-in state:
   - Logout links (`a[href*="logout"]`)
   - Control panel links (`a[href*="ucp.php?mode=profile"]`)
   - Text indicators ("logout", "user control panel", "my messages")

**Result:** If found, returns True (already logged in, skip login)

#### 4b. Perform Login (if needed)
```python
return await self._perform_login()
```

**Actions:**
1. Navigates to `BASE_URL/ucp.php?mode=login`
2. Handles any Cloudflare challenge automatically
3. **Displays message: "Please complete login in the browser window…"**
4. Polls page content every 5 seconds (up to 300 seconds)
5. Checks for login success indicators:
   - "logout" in page content
   - "user control panel" in page content
   - "welcome back" in page content
6. When successful:
   - **Saves session to `session.json`**
   - Returns True

**Result:** User is now authenticated, session persisted

### 5. Execute Selected Task
```python
if args.task == "members":
    await run_member_scrape(session, args)
```

**Actions:**
1. Calls appropriate task function
2. Task uses `session.make_request(url)` for all HTTP requests
3. All requests use the authenticated browser session

#### 5a. Request Flow (`session.make_request()`)
```python
response = await self.page.goto(url, wait_until="domcontentloaded")
await asyncio.sleep(2)
content = await self.page.content()
```

**Cloudflare Detection:**
```python
if any(token in content for token in ("Just a moment", "cf-challenge", ...)):
    await self._handle_cloudflare_challenge()
```

**Actions:**
1. Browser navigates to URL (real page load, not API call)
2. Waits for DOM to load
3. Checks for Cloudflare challenge indicators
4. If detected, waits for challenge to complete automatically
5. Returns page content

**Result:** All requests bypass Cloudflare, using authenticated session

### 6. Session Cleanup
```python
async with SessionManager(...) as session:
    # ... tasks run ...
# __aexit__ is called here
```

#### 6a. Save Session on Exit
```python
await self.context.storage_state(path=self.session_file)
```

**Actions:**
1. Saves current cookies and storage state
2. Writes to `session.json`
3. Closes browser
4. Stops Playwright

**Result:** Session persisted for next run

## Session File Format

`session.json` contains:
```json
{
  "cookies": [
    {
      "name": "phpbb3_*_sid",
      "value": "...",
      "domain": "forum.example.com",
      "path": "/",
      ...
    }
  ],
  "origins": [...]
}
```

## Cloudflare Mitigation

### Why It Works

1. **Real Browser**: Uses actual Chromium, not HTTP client
2. **Stealth Mode**: Disables automation detection flags
3. **Proper Fingerprint**: Real viewport, User-Agent, headers
4. **Automatic Solving**: Browser solves challenges without intervention
5. **Session Persistence**: Cookies carry trust/reputation across runs

### Challenge Detection

Checks for these strings in page content:
- "Just a moment"
- "cf-challenge"
- "challenge-platform"
- "checking your browser"
- "verifying you are human"
- "cloudflare"

### Challenge Handling

1. Detected during `make_request()`
2. Calls `_handle_cloudflare_challenge()`
3. Polls page every 3 seconds (up to 120 seconds)
4. Waits for challenge strings to disappear
5. Returns when page is clean

## Verification

To verify the flow works:

1. First run (no session):
   ```bash
   python main.py --task members --start 1 --stop 1 --show-browser --force-login
   ```
   - Browser window opens ✓
   - Navigates to login page ✓
   - User logs in manually ✓
   - `session.json` created ✓
   - Task executes ✓

2. Second run (session exists):
   ```bash
   python main.py --task members --start 2 --stop 2
   ```
   - Browser starts headless ✓
   - Loads `session.json` ✓
   - Detects already logged in ✓
   - Skips login page ✓
   - Task executes immediately ✓

## Summary

✅ User runs script → Browser opens
✅ Session loaded from `session.json` (if exists)
✅ Login detected OR user logs in manually
✅ Session saved to `session.json`
✅ Selected task runs with authenticated session
✅ Cloudflare challenges handled automatically
✅ Session persisted on exit

All requirements met!
