import requests
import sqlite3
from datetime import datetime, timedelta

SOURCE_NAME = "Strip District Terminal"
DB_PATH = "events.db"
DEFAULT_COLOR = "#DAA520"
GENRE = "Community"
BASE_URL = "https://www.stripdistrictterminal.com"
JSON_URL = f"{BASE_URL}/_next/data/Trg7AFDl4NR32exXccc68/happenings.json"

WEEKDAY_MAP = {
    "mo": 0,
    "tu": 1,
    "we": 2,
    "th": 3,
    "fr": 4,
    "sa": 5,
    "su": 6,
}

def fetch_all_events():
    print("[→] Fetching event data from JSON API...")
    response = requests.get(JSON_URL, headers={"User-Agent": "Mozilla/5.0"})
    if response.status_code != 200:
        print(f"[✖] Failed to load JSON: HTTP {response.status_code}")
        return []

    try:
        data = response.json()["pageProps"]["data"]
    except Exception as e:
        print(f"[✖] JSON parsing error: {e}")
        return []

    all_events = []

    # One-time events
    for ev in data.get("events", []):
        try:
            title = ev.get("title", "Untitled Event")
            desc = extract_description(ev.get("description", []))
            slug = ev.get("slug", {}).get("current", "")
            link = f"{BASE_URL}/happenings/{slug}"
            start_date = ev.get("datetime")
            end_date = ev.get("endDatetime") or start_date

            dt_start = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
            dt_end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))

            all_events.append({
                "title": title,
                "date": dt_start.isoformat(),
                "end": dt_end.isoformat(),
                "link": link,
                "description": desc
            })

            print(f"[✔] Added one-time event: {title} @ {dt_start.date()}")

        except Exception as e:
            print(f"[⚠️] Skipped one-time event: {e}")

    # Recurring events
    for ev in data.get("recurringEventTypes", []):
        try:
            title = ev.get("title", "Untitled Recurring Event")
            desc = extract_description(ev.get("description", []))
            slug = ev.get("slug", {}).get("current", "")
            config = ev.get("recurringConfig", {})
            freq = [WEEKDAY_MAP[f.lower()] for f in config.get("frequency", []) if f.lower() in WEEKDAY_MAP]
            if not freq:
                continue

            start_date = datetime.fromisoformat(config["startDate"])
            end_date = datetime.fromisoformat(config["endDate"])
            start_time = config.get("startTime", "10:00")
            end_time = config.get("endTime", "14:00")

            cur_date = start_date
            while cur_date <= end_date:
                if cur_date.weekday() in freq:
                    start_dt = datetime.fromisoformat(f"{cur_date.date()}T{start_time}")
                    end_dt = datetime.fromisoformat(f"{cur_date.date()}T{end_time}")
                    link = f"{BASE_URL}/happenings/event-type/{slug}/event?date={start_dt.isoformat()}"

                    all_events.append({
                        "title": title,
                        "date": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "link": link,
                        "description": desc
                    })
                    print(f"[↻] Added recurring: {title} on {cur_date.strftime('%Y-%m-%d')}")
                cur_date += timedelta(days=1)

        except Exception as e:
            print(f"[⚠️] Skipped recurring event: {e}")

    return all_events

def extract_description(blocks):
    return " ".join(
        span.get("text", "")
        for block in blocks if block.get("_type") == "block"
        for span in block.get("children", []) if span.get("_type") == "span"
    ).strip()

def save_to_db(events):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Ensure genre column exists
    c.execute("PRAGMA table_info(events)")
    columns = [row[1] for row in c.fetchall()]
    if "genre" not in columns:
        c.execute("ALTER TABLE events ADD COLUMN genre TEXT")

    today = datetime.today().strftime("%Y-%m-%d")
    c.execute("DELETE FROM events WHERE source = ? AND date >= ?", (SOURCE_NAME, today))

    added = 0
    for event in events:
        c.execute("SELECT 1 FROM events WHERE title = ? AND date = ? AND source = ?",
                  (event["title"], event["date"], SOURCE_NAME))
        if c.fetchone():
            continue

        c.execute("""
            INSERT INTO events (title, date, end, allDay, description, link, color, source, genre)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            event["title"],
            event["date"],
            event["end"],
            0,
            event["description"],
            event["link"],
            DEFAULT_COLOR,
            SOURCE_NAME,
            GENRE
        ))
        added += 1

    conn.commit()
    conn.close()
    print(f"[✔] Saved {added} events to {DB_PATH}")

if __name__ == "__main__":
    events = fetch_all_events()
    save_to_db(events)
    print(f"[ℹ️] Total events scraped: {len(events)}")
