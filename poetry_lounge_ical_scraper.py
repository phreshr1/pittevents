
import requests
from icalendar import Calendar
from datetime import datetime
import sqlite3

# URL for Poetry Lounge's ICS feed
ICAL_URL = "https://www.poetrymillvale.com/events?ical=1"
SOURCE_NAME = "Poetry Lounge"
COLOR = "#8A2BE2"  # A distinct color for calendar events

# Download the ICS
response = requests.get(ICAL_URL)
response.raise_for_status()

cal = Calendar.from_ical(response.content)
events = []

for component in cal.walk():
    if component.name != "VEVENT":
        continue

    title = str(component.get("summary", "No Title"))
    start = component.get("dtstart").dt
    end = component.get("dtend").dt
    description = str(component.get("description", "")).strip()
    location = str(component.get("location", "")).strip()

    # Format datetimes
    def fmt(dt):
        return dt.strftime("%Y-%m-%dT%H:%M:%S") if isinstance(dt, datetime) else dt.strftime("%Y-%m-%dT00:00:00")

    events.append({
        "title": title,
        "date": fmt(start),
        "end": fmt(end),
        "link": "https://www.poetrymillvale.com/events/",
        "description": description,
        "venue": location or "Poetry Lounge, 313 North Ave"
    })

# Save to local SQLite
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Ensure table columns exist
cursor.execute("PRAGMA table_info(events)")
cols = [c[1] for c in cursor.fetchall()]
for col in ("description", "genre", "venue", "price"):
    if col not in cols:
        cursor.execute(f"ALTER TABLE events ADD COLUMN {col} TEXT")

# Remove old Poetry Lounge entries
cursor.execute("DELETE FROM events WHERE source = ?", (SOURCE_NAME,))

# Insert fresh events
for e in events:
    cursor.execute("""
        INSERT INTO events (title, date, end, link, allDay, color, source, description, venue)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        e["title"], e["date"], e["end"], e["link"], 0,
        COLOR, SOURCE_NAME, e["description"], e["venue"]
    ))

conn.commit()
conn.close()

print(f"[✓] Loaded {len(events)} Poetry Lounge events from ICS.")
