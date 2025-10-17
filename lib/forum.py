#!/usr/bin/env python3
"""
Forum scraper module for DarkForum
"""

import requests
import time
import asyncio
from bs4 import BeautifulSoup
from lib.storage import store_data
from config import HEADERS, BASE_URL
from lib.session_manager import SessionManager
import topic


async def scrape_all_forums_async(delay=1.0, limit_pages=None):
    """
    Async forum scraping using session manager
    """
    print("[>] Starting forum scraping...")
    
    async with SessionManager() as session:
        # Ensure we're logged in
        await session.ensure_logged_in()
        
        # Get forum index
        forum_index_url = f"{BASE_URL}index.php"
        
        try:
            response = await session.make_request(forum_index_url)
            if not response:
                print("[!] Failed to fetch forum index")
                return
                
            html = response.get("content", "")
            soup = BeautifulSoup(html, 'lxml')
            
            # Find all forum links
            forum_links = soup.find_all('a', href=True)
            forums = []
            
            print(f"[*] Found {len(forum_links)} total links on page")
            
            for link in forum_links:
                href = link.get('href', '')
                if 'viewforum.php?f=' in href:
                    # Extract forum ID
                    try:
                        forum_id = href.split('f=')[1].split('&')[0]
                        forum_name = link.get_text(strip=True)
                        if forum_name:  # Only add if name is not empty
                            forums.append({
                                'forum_id': int(forum_id),
                                'forum_name': forum_name,
                                'forum_url': f"{BASE_URL}{href}"
                            })
                            print(f"  [+] Found forum: {forum_name} (ID: {forum_id})")
                    except (ValueError, IndexError):
                        continue
            
            # If no forums found, try alternative selectors
            if not forums:
                print("[*] No forums found with standard selector, trying alternatives...")
                # Try looking for forum categories or other patterns
                category_links = soup.find_all('a', href=True)
                for link in category_links:
                    href = link.get('href', '')
                    if 'forum' in href.lower() and 'f=' in href:
                        try:
                            forum_id = href.split('f=')[1].split('&')[0]
                            forum_name = link.get_text(strip=True)
                            if forum_name:
                                forums.append({
                                    'forum_id': int(forum_id),
                                    'forum_name': forum_name,
                                    'forum_url': f"{BASE_URL}{href}"
                                })
                                print(f"  [+] Found forum (alt): {forum_name} (ID: {forum_id})")
                        except (ValueError, IndexError):
                            continue
            
            print(f"[+] Found {len(forums)} forums")
            
            # Scrape each forum
            for forum in forums:
                print(f"\n[>] Scraping forum: {forum['forum_name']} (ID: {forum['forum_id']})")
                await scrape_forum_topics_async(session, forum, delay, limit_pages)
                await asyncio.sleep(delay)
                
        except Exception as e:
            print(f"[!] Error scraping forums: {e}")


def scrape_all_forums(delay=1.0, limit_pages=None):
    """
    Scrape all forums and their topics (sync wrapper)
    """
    asyncio.run(scrape_all_forums_async(delay, limit_pages))


async def scrape_forum_topics_async(session: SessionManager, forum, delay=1.0, limit_pages=None):
    """
    Async forum topics scraping using session manager
    """
    forum_id = forum['forum_id']
    page = 0
    
    while True:
        if limit_pages and page >= limit_pages:
            break
            
        url = f"{BASE_URL}viewforum.php?f={forum_id}&start={page * 30}"
        
        try:
            response = await session.make_request(url)
            if not response:
                print(f"[!] Failed to fetch forum {forum_id} page {page}")
                break
                
            html = response.get("content", "")
            soup = BeautifulSoup(html, 'lxml')
            
            # Check if we've reached the end
            if "No posts found" in html or "No topics found" in html:
                break
                
            # Find topic links
            topic_links = soup.find_all('a', href=True)
            topics = []
            
            for link in topic_links:
                href = link.get('href', '')
                if 'viewtopic.php?t=' in href:
                    try:
                        topic_id = href.split('t=')[1].split('&')[0]
                        topic_title = link.get_text(strip=True)
                        topics.append({
                            'forum_id': forum_id,
                            'topic_id': int(topic_id),
                            'topic_title': topic_title,
                            'topic_url': f"{BASE_URL}{href}"
                        })
                    except (ValueError, IndexError):
                        continue
            
            if not topics:
                break
                
            print(f"  [+] Found {len(topics)} topics on page {page + 1}")
            
            # Store topics
            store_data("forum_topics", topics)
            
            # Also scrape thread content for each topic
            for topic in topics:
                print(f"    [>] Scraping content from topic: {topic['topic_title']}")
                await scrape_topic_content_async(session, topic, delay)
            
            page += 1
            await asyncio.sleep(delay)
            
        except Exception as e:
            print(f"[!] Error scraping forum {forum_id} page {page}: {e}")
            break


def scrape_forum_topics(session, forum, delay=1.0, limit_pages=None):
    """
    Legacy sync version - kept for compatibility
    """
    forum_id = forum['forum_id']
    page = 0
    
    while True:
        if limit_pages and page >= limit_pages:
            break
            
        url = f"{BASE_URL}viewforum.php?f={forum_id}&start={page * 30}"
        
        try:
            response = session.get(url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'lxml')
            
            # Check if we've reached the end
            if "No posts found" in response.text or "No topics found" in response.text:
                break
                
            # Find topic links
            topic_links = soup.find_all('a', href=True)
            topics = []
            
            for link in topic_links:
                href = link.get('href', '')
                if 'viewtopic.php?t=' in href:
                    try:
                        topic_id = href.split('t=')[1].split('&')[0]
                        topic_title = link.get_text(strip=True)
                        topics.append({
                            'forum_id': forum_id,
                            'topic_id': int(topic_id),
                            'topic_title': topic_title,
                            'topic_url': f"{BASE_URL}{href}"
                        })
                    except (ValueError, IndexError):
                        continue
            
            if not topics:
                break
                
            print(f"  [+] Found {len(topics)} topics on page {page + 1}")
            
            # Store topics
            store_data("forum_topics", topics)
            
            # Also scrape thread content for each topic
            for topic in topics:
                print(f"    [>] Scraping content from topic: {topic['topic_title']}")
                scrape_topic_content(session, topic, delay)
            
            page += 1
            time.sleep(delay)
            
        except Exception as e:
            print(f"[!] Error scraping forum {forum_id} page {page}: {e}")
            break


async def scrape_topic_content_async(session: SessionManager, topic, delay=1.0):
    """
    Async topic content scraping using session manager
    """
    try:
        # Create print view URL for the topic
        topic_url = topic['topic_url']
        if 'viewtopic.php' in topic_url:
            # Convert to print view
            if '?' in topic_url:
                print_url = topic_url + '&view=print'
            else:
                print_url = topic_url + '?view=print'
        else:
            print_url = topic_url
        
        print(f"      [>] Scraping: {print_url}")
        
        # Use the session manager to get the content
        response = await session.make_request(print_url)
        if not response:
            print(f"      [!] Failed to fetch topic {topic['topic_id']}")
            return
            
        html = response.get("content", "")
        
        # Parse the content using the topic parser
        parsed = topic.parse_print_view(html)
        
        if parsed.get("error"):
            print(f"      [!] Error in topic {topic['topic_id']}: {parsed.get('message', 'Unknown error')}")
            return
            
        posts = parsed.get("posts", [])
        
        if posts:
            # Store the posts with topic context
            for post in posts:
                post['forum_id'] = topic['forum_id']
                post['topic_id'] = topic['topic_id']
                post['topic_title'] = topic['topic_title']
            
            store_data("thread_posts", posts)
            print(f"      [+] Scraped {len(posts)} posts from topic {topic['topic_id']}")
        else:
            print(f"      [!] No posts found in topic {topic['topic_id']}")
            
    except Exception as e:
        print(f"      [!] Error scraping topic {topic['topic_id']}: {e}")


def scrape_topic_content(session, topic, delay=1.0):
    """
    Legacy sync version - kept for compatibility
    """
    try:
        # Create print view URL for the topic
        topic_url = topic['topic_url']
        if 'viewtopic.php' in topic_url:
            # Convert to print view
            if '?' in topic_url:
                print_url = topic_url + '&view=print'
            else:
                print_url = topic_url + '?view=print'
        else:
            print_url = topic_url
        
        print(f"      [>] Scraping: {print_url}")
        
        # Use the topic scraper to get all posts
        all_posts = topic.scrape_all_pages_for_topic(
            session, 
            topic['forum_id'], 
            topic['topic_id'], 
            step=10, 
            pause=delay
        )
        
        if all_posts:
            # Store the posts with topic context
            for post in all_posts:
                post['forum_id'] = topic['forum_id']
                post['topic_id'] = topic['topic_id']
                post['topic_title'] = topic['topic_title']
            
            store_data("thread_posts", all_posts)
            print(f"      [+] Scraped {len(all_posts)} posts from topic {topic['topic_id']}")
        else:
            print(f"      [!] No posts found in topic {topic['topic_id']}")
            
    except Exception as e:
        print(f"      [!] Error scraping topic {topic['topic_id']}: {e}")


if __name__ == "__main__":
    scrape_all_forums()
