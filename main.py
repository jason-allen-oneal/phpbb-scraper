#!/usr/bin/env python3
"""
DarkForum Scraper - Unified Entry Point
"""

import argparse
import sys
import time
from pathlib import Path

from lib.storage import init_storage, close_storage
import topic
import member
import forum


OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def run_thread_scrape(args):
    if not args.url:
        print("[!] --url required for task=thread")
        sys.exit(2)
    print(f"[>] Running thread scraper → {args.url}")
    base_print = args.url + ("&" if ("?" in args.url) else "?") + "view=print"
    topic.scrape_all_pages(
        base_print_url=base_print,
        start=args.start,
        stop=args.stop,
        step=args.step,
        pause=args.delay,
        out_collection="thread_posts"
    )


def run_member_scrape(args):
    print("[>] Running member scraper (UID enumeration)")
    member.scrape_members(
        start_uid=args.start or 1,
        stop_uid=args.stop,
        delay=args.delay
    )


def run_forum_index(args):
    print("[>] Running forum indexer")
    forum.scrape_all_forums(delay=args.delay, limit_pages=args.limit_pages)


def run_all(args):
    """
    Run full scrape sequence:
      1. Member list + profiles
      2. Forum index + topics
    """
    print("[>] Running full ALL task (members → forums → threads)")
    # Step 1: Members
    member.scrape_members(
        start_uid=args.start or 1,
        stop_uid=args.stop,
        delay=args.delay
    )
    # Step 2: Forums + Topics
    forum.scrape_all_forums(delay=args.delay, limit_pages=args.limit_pages)
    print("[✔] Completed ALL task sequence.")


def main():
    parser = argparse.ArgumentParser(description="DarkForum Scraper Controller")
    parser.add_argument(
        "--task", required=True,
        choices=["thread", "members", "forums", "all"],
        help="Which scrape to run (thread | members | forums | all)"
    )
    parser.add_argument("--url", help="Topic URL when task=thread")
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--start", type=int, default=1, help="Starting UID or topic index")
    parser.add_argument("--stop", type=int, default=None, help="Stop UID or topic index")
    parser.add_argument("--step", type=int, default=10)
    parser.add_argument("--limit-pages", type=int, default=None, help="Limit forum pages per forum")
    args = parser.parse_args()

    init_storage()
    start_time = time.time()

    try:
        if args.task == "thread":
            run_thread_scrape(args)
        elif args.task == "members":
            run_member_scrape(args)
        elif args.task == "forums":
            run_forum_index(args)
        elif args.task == "all":
            run_all(args)
        else:
            print("Unknown task type.")
            sys.exit(1)
    finally:
        close_storage()

    elapsed = time.time() - start_time
    print(f"\n[✔] Completed in {elapsed:.2f}s")


if __name__ == "__main__":
    main()
