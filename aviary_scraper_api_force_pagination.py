
import requests
import sqlite3
import html
from datetime import datetime, timedelta

API_URL = "https://www.aviary.org/wp-json/tribe/events/v1/events"

start_date = datetime.today().strftime("%Y-%m-%d")
end_date = (datetime.today() + timedelta(days=120)).strftime("%Y-%m-%d")

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
}

# Fetch all pages until we get < 50 results
all_events = []
page = 1
while True:
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "per_page": 50,
        "page": page
    }
    response = requests.get(API_URL, params=params, headers=headers)
    data = response.json()
    events = data.get("events", [])
    print(f"[Page {page}] Retrieved {len(events)} events.")
    all_events.extend(events)
    if len(events) < 50:
        break
    page += 1

# Connect to DB
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Ensure description column exists
cursor.execute("PRAGMA table_info(events)")
columns = [row[1] for row in cursor.fetchall()]
if "description" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN description TEXT")

cursor.execute("DELETE FROM events WHERE source = 'Aviary' AND date >= ? AND date <= ?", (start_date, end_date))

added = 0
skipped = 0
for event in all_events:
    raw_title = event["title"].strip()
    if "daily activities" in raw_title.lower():
        skipped += 1
        continue

    title = html.unescape(raw_title)
    start = event["start_date"]
    end = event["end_date"]
    url = event["url"]
    all_day = 1 if event.get("all_day", False) else 0
    description = html.unescape(event.get("description", "")).strip()

    if start.startswith("2025-08-02"):
        print(f"[Check] Found event on Aug 2: {title}")

    cursor.execute("SELECT 1 FROM events WHERE title = ? AND date = ? AND source = ?", (title, start, "Aviary"))
    if cursor.fetchone():
        continue

    cursor.execute("""
        INSERT INTO events (title, date, end, link, allDay, color, source, description)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (title, start, end, url, all_day, "#0077b6", "Aviary", description))
    added += 1

conn.commit()
conn.close()

print(f"[✓] Loaded {added} Aviary events from {start_date} to {end_date}.")
print(f"[•] Skipped {skipped} events due to filter.")
