#!/usr/bin/env python3
"""Unified entry point for the DarkForum scraper."""

from __future__ import annotations

import argparse
import asyncio
import sys
import time

from lib.session_manager import SessionManager
from lib.storage import close_storage, init_storage
import members
from lib import forum
import topic


async def run_thread_scrape(session: SessionManager, args: argparse.Namespace) -> None:
    if not args.url:
        print("[!] --url is required when task=thread")
        sys.exit(2)

    print(f"[>] Running thread scraper → {args.url}")
    await topic.scrape_thread_from_url(
        session,
        args.url,
        start=args.start,
        stop=args.stop,
        step=args.step,
        delay=args.delay,
    )


async def run_member_scrape(session: SessionManager, args: argparse.Namespace) -> None:
    print("[>] Running member scraper (UID enumeration)")
    await members.scrape_members(
        session=session,
        start_uid=args.start,
        stop_uid=args.stop,
        delay=args.delay,
    )


async def run_forum_index(session: SessionManager, args: argparse.Namespace) -> None:
    print("[>] Running forum indexer")
    await forum.scrape_all_forums(session=session, delay=args.delay, limit_pages=args.limit_pages)


async def run_all(session: SessionManager, args: argparse.Namespace) -> None:
    print("[>] Running COMPLETE ALL task (members → forums → thread content)")

    print("\n=== STEP 1: MEMBER SCRAPING ===")
    await run_member_scrape(session, args)

    print("\n=== STEP 2: FORUM SCRAPING ===")
    await run_forum_index(session, args)

    print("[✔] Completed COMPLETE ALL task sequence.")
    print("[+] Scraped: Members + Forum Structure + Thread Content")


async def dispatch(args: argparse.Namespace) -> None:
    async with SessionManager(headless=not args.show_browser) as session:
        await session.ensure_logged_in(force_login=args.force_login)

        if args.task == "thread":
            await run_thread_scrape(session, args)
        elif args.task == "members":
            await run_member_scrape(session, args)
        elif args.task == "forums":
            await run_forum_index(session, args)
        elif args.task == "all":
            await run_all(session, args)
        else:  # pragma: no cover - argparse enforces choices
            print("Unknown task type.")
            sys.exit(1)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="DarkForum Scraper Controller")
    parser.add_argument(
        "--task",
        required=True,
        choices=["thread", "members", "forums", "all"],
        help="Which scrape to run",
    )
    parser.add_argument("--url", help="Topic URL when task=thread")
    parser.add_argument("--delay", type=float, default=1.0, help="Delay between requests")
    parser.add_argument("--start", type=int, default=1, help="Starting UID or page offset")
    parser.add_argument("--stop", type=int, default=None, help="Stop UID or page offset")
    parser.add_argument("--step", type=int, default=10, help="Pagination step for thread scraping")
    parser.add_argument("--limit-pages", type=int, default=None, help="Limit forum pages per forum")
    parser.add_argument("--show-browser", action="store_true", help="Run Playwright in headed mode")
    parser.add_argument("--force-login", action="store_true", help="Force a fresh login")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    init_storage()
    start_time = time.time()

    try:
        asyncio.run(dispatch(args))
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user")
    finally:
        close_storage()

    elapsed = time.time() - start_time
    print(f"\n[✔] Completed in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
