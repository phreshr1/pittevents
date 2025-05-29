
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import sqlite3
import re

SOURCE = "Lawrence Convention Center"
COLOR = "#A52A2A"
BASE_URL = "https://54735888.calendar.conventioncalendar.com/events/load?page={}"
HEADERS = {"User-Agent": "Mozilla/5.0"}
MAX_PAGES = 20
CUTOFF_DATE = datetime.now() + timedelta(days=730)

def parse_event_card(card):
    try:
        title_elem = card.select_one("h5 a")
        if not title_elem:
            return []
        title = title_elem.get_text(strip=True)
        link = title_elem.get("href", "#")

        calendar_icon = card.find("i", class_="fal fa-calendar-alt")
        date_text = calendar_icon.next_sibling.strip() if calendar_icon else ""
        date_range = re.findall(r"(\d{2} \w+ \d{4})", date_text)
        if not date_range:
            return []

        start_date = datetime.strptime(date_range[0], "%d %b %Y")
        end_date = datetime.strptime(date_range[-1], "%d %b %Y") if len(date_range) > 1 else start_date

        if start_date > CUTOFF_DATE:
            return []

        location_elem = card.select_one("h6 a")
        location = location_elem.get_text(strip=True) if location_elem else "David L. Lawrence Convention Center"
        desc = title_elem.get("title", "").strip() or title

        events = []
        current_date = start_date
        while current_date <= end_date and current_date <= CUTOFF_DATE:
            date_iso = current_date.strftime("%Y-%m-%d")  # no time = all-day
            events.append({
                "title": title,
                "date": date_iso,
                "link": link,
                "description": f"{desc} (Location: {location})"
            })
            current_date += timedelta(days=1)

        return events
    except Exception:
        return []

def fetch_all_events():
    all_events = []
    for page in range(1, MAX_PAGES + 1):
        url = BASE_URL.format(page)
        print(f"[...] Fetching page {page}")
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
        except Exception as e:
            print(f"[!] Request failed for page {page}: {e}")
            break

        if res.status_code != 200 or "event-card" not in res.text:
            break

        soup = BeautifulSoup(res.text, "html.parser")
        cards = soup.select(".event-card")
        found_valid = False

        for card in cards:
            events = parse_event_card(card)
            if events:
                all_events.extend(events)
                found_valid = True

        if not found_valid:
            print("[!] No valid events on this page. Stopping early.")
            break

    return all_events

# Load and save to database
events = fetch_all_events()
conn = sqlite3.connect("events.db")
cursor = conn.cursor()
cursor.execute("DELETE FROM events WHERE source = ?", (SOURCE,))
for e in events:
    cursor.execute("""
    INSERT INTO events (title, date, end, link, allDay, color, source, description)
    VALUES (?, ?, NULL, ?, 1, ?, ?, ?)
""", (
        e["title"], e["date"], e["link"], COLOR, SOURCE, e["description"]
    ))
conn.commit()
conn.close()

print(f"[✓] Loaded {len(events)} individual day-events from {SOURCE}.")
