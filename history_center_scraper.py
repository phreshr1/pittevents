import requests
from bs4 import BeautifulSoup
import sqlite3
from datetime import datetime
import re

BASE_URL = "https://www.heinzhistorycenter.org/events/"
SOURCE = "Heinz History Center"
COLOR = "#FF0000"

def extract_events_from_page(page_num):
    url = f"{BASE_URL}?current_page={page_num}"
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select("div.card")

    events = []

    for card in cards:
        try:
            title = card.select_one(".card_title_link_label").get_text(strip=True)
            date_raw = card.select_one(".card_date").get_text(strip=True)
            time_raw = card.select_one(".card_time").get_text(strip=True)
            location = card.select_one(".card_location").get_text(strip=True)
            description_elem = card.select_one(".card_description p")
            description = description_elem.get_text(strip=True) if description_elem else ""
            link_elem = card.select_one(".card_title a")
            link = link_elem["href"] if link_elem else BASE_URL

            # Parse datetime
            month_day_match = re.match(r"([A-Za-z]+)\s+(\d+)", date_raw)
            if not month_day_match:
                continue
            month, day = month_day_match.groups()
            year = datetime.now().year
            datetime_str = f"{month} {day} {year} {time_raw}"
            date = datetime.strptime(datetime_str, "%B %d %Y %I:%M %p")
            date_iso = date.strftime("%Y-%m-%dT%H:%M:%S")

            events.append({
                "title": title,
                "date": date_iso,
                "link": link,
                "description": description,
                "venue": location
            })
        except Exception as e:
            print(f"[!] Skipped card due to error: {e}")
            continue

    return events

# Connect to DB
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

# Ensure schema
cursor.execute("PRAGMA table_info(events)")
columns = [col[1] for col in cursor.fetchall()]
for col in ["description", "venue", "price", "genre"]:
    if col not in columns:
        cursor.execute(f"ALTER TABLE events ADD COLUMN {col} TEXT")

cursor.execute("DELETE FROM events WHERE source = ?", (SOURCE,))

# Loop over pages
page = 1
total_added = 0
while True:
    page_events = extract_events_from_page(page)
    if not page_events:
        break

    for e in page_events:
        cursor.execute("""
            INSERT INTO events (title, date, end, link, allDay, color, source, description, venue)
            VALUES (?, ?, NULL, ?, 0, ?, ?, ?, ?)
        """, (
            e["title"], e["date"], e["link"], COLOR, SOURCE, e["description"], e["venue"]
        ))
    total_added += len(page_events)
    page += 1

conn.commit()
conn.close()
print(f"[✓] Loaded {total_added} events from {SOURCE}.")
