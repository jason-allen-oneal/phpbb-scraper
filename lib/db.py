import mysql.connector
from mysql.connector import Error
from config import DB_HOST, DB_NAME, DB_USER, DB_PASS, DB_PORT
import json
from typing import List, Dict, Any, Optional


def get_connection():
    """Get a database connection"""
    try:
        conn = mysql.connector.connect(
            host=DB_HOST,
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            port=DB_PORT,
            charset='utf8mb4',
            autocommit=False
        )
        return conn
    except Error as e:
        print(f"[!] Database connection error: {e}")
        return None


def query(sql: str, params: Optional[tuple] = None) -> Optional[List[Dict[str, Any]]]:
    """Execute a SQL query and return results"""
    conn = get_connection()
    if not conn:
        return None
    
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute(sql, params or ())
        
        # Auto-detect: fetch results if SELECT, commit otherwise
        if sql.strip().lower().startswith("select"):
            result = cursor.fetchall()
        else:
            conn.commit()
            result = cursor.rowcount
        
        cursor.close()
        return result
        
    except Error as e:
        print(f"[!] Database query error: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()


def insert_members(members: List[Dict[str, Any]]) -> bool:
    """Insert member data into the database"""
    if not members:
        return True
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Prepare data for insertion
        insert_data = []
        for member in members:
            if member.get('error'):
                continue
                
            insert_data.append((
                member.get('uid'),
                member.get('username'),
                member.get('rank'),
                member.get('join_date'),
                member.get('total_posts'),
                member.get('location'),
                member.get('signature'),
                member.get('avatar'),
                json.dumps(member.get('links', [])) if member.get('links') else None
            ))
        
        if not insert_data:
            return True
        
        # Use INSERT ... ON DUPLICATE KEY UPDATE to handle existing records
        sql = """
            INSERT INTO members (uid, username, rank, join_date, total_posts, location, signature, avatar, links)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username = VALUES(username),
                rank = VALUES(rank),
                join_date = VALUES(join_date),
                total_posts = VALUES(total_posts),
                location = VALUES(location),
                signature = VALUES(signature),
                avatar = VALUES(avatar),
                links = VALUES(links)
        """
        
        cursor.executemany(sql, insert_data)
        conn.commit()
        
        print(f"[+] Inserted/updated {len(insert_data)} members")
        return True
        
    except Error as e:
        print(f"[!] Error inserting members: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def insert_forum_topics(topics: List[Dict[str, Any]]) -> bool:
    """Insert forum topics into the database"""
    if not topics:
        return True
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        insert_data = []
        for topic in topics:
            insert_data.append((
                topic.get('forum_id'),
                topic.get('topic_id'),
                topic.get('topic_title'),
                topic.get('topic_url')
            ))
        
        sql = """
            INSERT INTO forum_topics (forum_id, topic_id, topic_title, topic_url)
            VALUES (%s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                topic_title = VALUES(topic_title),
                topic_url = VALUES(topic_url)
        """
        
        cursor.executemany(sql, insert_data)
        conn.commit()
        
        print(f"[+] Inserted/updated {len(insert_data)} forum topics")
        return True
        
    except Error as e:
        print(f"[!] Error inserting forum topics: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def insert_thread_posts(posts: List[Dict[str, Any]], forum_id: Optional[int] = None, topic_id: Optional[int] = None) -> bool:
    """Insert thread posts into the database"""
    if not posts:
        return True
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        insert_data = []
        for post in posts:
            insert_data.append((
                forum_id,
                topic_id,
                post.get('author'),
                post.get('author_id'),
                post.get('timestamp'),
                post.get('content')
            ))
        
        sql = """
            INSERT INTO thread_posts (forum_id, topic_id, author, author_id, timestamp, content)
            VALUES (%s, %s, %s, %s, %s, %s)
        """
        
        cursor.executemany(sql, insert_data)
        conn.commit()
        
        print(f"[+] Inserted {len(insert_data)} thread posts")
        return True
        
    except Error as e:
        print(f"[!] Error inserting thread posts: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()


def insert_generic_data(collection: str, data: List[Dict[str, Any]]) -> bool:
    """Insert generic scraped data into the database"""
    if not data:
        return True
    
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        insert_data = []
        for item in data:
            insert_data.append((
                collection,
                json.dumps(item, ensure_ascii=False)
            ))
        
        sql = """
            INSERT INTO scraped_data (collection, data)
            VALUES (%s, %s)
        """
        
        cursor.executemany(sql, insert_data)
        conn.commit()
        
        print(f"[+] Inserted {len(insert_data)} items into collection '{collection}'")
        return True
        
    except Error as e:
        print(f"[!] Error inserting generic data: {e}")
        conn.rollback()
        return False
    finally:
        cursor.close()
        conn.close()