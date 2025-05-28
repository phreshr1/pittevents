
import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
import html

RSS_FEED_URL = "https://culturaldistrict.org/feed?format=rss"

response = requests.get(RSS_FEED_URL)
soup = BeautifulSoup(response.content, features="xml")

items = soup.find_all("item")

conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(events)")
columns = [row[1] for row in cursor.fetchall()]
if "description" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN description TEXT")

today = datetime.today().strftime("%Y-%m-%d")
cursor.execute("DELETE FROM events WHERE source = 'Cultural District' AND date >= ?", (today,))

added = 0
for item in items:
    try:
        title = html.unescape(item.title.text.strip()) if item.title else "Untitled"
        date_text = item.find("date").text.strip() if item.find("date") else None
        time_text = item.find("time").text.strip() if item.find("time") else "7:00PM"  # default if missing
        link = item.link.text.strip() if item.link else ""
        description = html.unescape(item.description.text.strip()) if item.description else ""

        if not date_text:
            print(f"[!] Skipped item: missing <date>")
            continue

        # Combine date and time
        combined_str = f"{date_text}, {time_text}"  # e.g. "Fri, Jun 13, 2025, 7:00PM"
        try:
            date_obj = datetime.strptime(combined_str, "%a, %b %d, %Y, %I:%M%p")
        except ValueError:
            print(f"[!] Bad date format: {combined_str}")
            continue

        date_iso = date_obj.strftime("%Y-%m-%dT%H:%M:%S")  # full datetime format for calendar
        end_time = None  # Not provided in RSS

        cursor.execute("SELECT 1 FROM events WHERE title = ? AND date = ? AND source = ?", (title, date_iso, "Cultural District"))
        if cursor.fetchone():
            continue

        cursor.execute("""
            INSERT INTO events (title, date, end, link, allDay, color, source, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, date_iso, end_time, link, 0, "#8B008B", "Cultural District", description))
        added += 1
    except Exception as e:
        print(f"[!] Skipped item due to error: {e}")

conn.commit()
conn.close()
print(f"[✓] Loaded {added} Cultural District events with times from RSS.")
