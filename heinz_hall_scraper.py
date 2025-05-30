import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
import html

RSS_FEED_URL = "https://www.pittsburghsymphony.org/feed?format=rss"
SOURCE_NAME = "Heinz Hall"
COLOR = "#B22222"

# Fetch and parse RSS feed
response = requests.get(RSS_FEED_URL)
soup = BeautifulSoup(response.content, features="xml")
items = soup.find_all("item")

# Connect to database
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Ensure optional columns exist
cursor.execute("PRAGMA table_info(events)")
columns = [row[1] for row in cursor.fetchall()]
if "description" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN description TEXT")
if "genre" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN genre TEXT")
if "venue" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN venue TEXT")
if "price" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN price TEXT")

# Remove old entries from this source
today = datetime.today().strftime("%Y-%m-%d")
cursor.execute("DELETE FROM events WHERE source = ? AND date >= ?", (SOURCE_NAME, today))

added = 0
for item in items:
    try:
        title = html.unescape(item.title.text.strip()) if item.title else "Untitled"
        link = item.link.text.strip() if item.link else ""
        description = html.unescape(item.description.text.strip()) if item.description else ""
        datetime_str = item.find("datetime").text.strip() if item.find("datetime") else None
        venue = item.find("venue").text.strip() if item.find("venue") else "Heinz Hall"

        if not datetime_str:
            continue

        # Format: "Fri, May 30, 2025, 7:30PM"
        try:
            dt = datetime.strptime(datetime_str, "%a, %b %d, %Y, %I:%M%p")
        except ValueError:
            continue

        date_iso = dt.strftime("%Y-%m-%dT%H:%M:%S")

        # Skip duplicates
        cursor.execute("SELECT 1 FROM events WHERE title = ? AND date = ? AND source = ?", (title, date_iso, SOURCE_NAME))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO events (title, date, end, link, allDay, color, source, description, venue)
            VALUES (?, ?, NULL, ?, ?, ?, ?, ?, ?)
        """, (title, date_iso, link, 0, COLOR, SOURCE_NAME, description, venue))

        added += 1
    except Exception as e:
        print(f"[!] Skipped due to error: {e}")

conn.commit()
conn.close()
print(f"[✓] Loaded {added} Heinz Hall events from RSS.")
