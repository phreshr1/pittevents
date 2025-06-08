import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import json
import sqlite3
from date_parser_hybrid import parse_flexible_date_range

# Add a mapping from raw category names to display names (title case, nice formatting)
CATEGORY_DISPLAY_MAP = {
    "ARTS + CULTURE": "Arts & Culture",
    "COMMUNITY": "Community",
    "CONVENTION": "Convention",
    "ENTERTAINMENT": "Entertainment",
    "FAMILY": "Family",
    "FESTIVAL": "Festival",
    "FILM & MOVIES": "Film & Movies",
    "HOLIDAYS": "Holidays",
    "MARKET SQUARE": "Market Square",
    "MUSIC": "Music",
    "NIGHTLIFE": "Nightlife",
    "ONLINE & VIRTUAL EVENTS": "Online & Virtual Events",
    "OUTDOOR": "Outdoor",
    "PDP EVENTS": "PDP Events",
    "SHOPPING": "Shopping",
    "SPORTS + RECREATION": "Sports & Recreation",
    "TOURS": "Tours",
    "WORKSHOPS & CLASSES": "Workshops & Classes"
}

def normalize_categories(raw_categories):
    """Convert raw categories to display names using CATEGORY_DISPLAY_MAP."""
    return [
        CATEGORY_DISPLAY_MAP.get(cat.upper(), cat.title())
        for cat in raw_categories
    ]

def scrape_downtown_pittsburgh_events():
    url = "https://downtownpittsburgh.com/events/"
    resp = requests.get(url)
    soup = BeautifulSoup(resp.text, "html.parser")
    events = []
    for event_card in soup.select("div.copyContent"):
        # Categories
        raw_categories = [t.get_text(strip=True).rstrip(',') for t in event_card.select(".category .term")]
        categories = normalize_categories(raw_categories)
        # Title
        title_tag = event_card.select_one("h1 a")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled Event"
        # URL
        url = title_tag['href'] if title_tag and title_tag.has_attr('href') else ''
        if url and url.startswith('/'):
            url = f"https://downtownpittsburgh.com{url}"
        # Date and time
        eventdate = event_card.select_one(".eventdate")
        date_str, time_str = '', ''
        if eventdate:
            # Robustly extract date and time from eventdate
            eventdate_text = eventdate.get_text(separator="|", strip=True)
            parts = [p.strip() for p in eventdate_text.split('|')]
            date_str = parts[0] if len(parts) > 0 else ''
            time_str = parts[1] if len(parts) > 1 else ''
        # Description
        desc = event_card.get_text(" ", strip=True)
        # Debug print
        print(f"Scraping event: {title}\n  date_str: '{date_str}'\n  time_str: '{time_str}'\n  categories: {categories}")

        # Use robust date parser
        current_year = datetime.now().year
        date_tuple = parse_flexible_date_range(date_str, current_year) if date_str else None
        if date_tuple:
            start, end = date_tuple
            delta = (end - start).days
            if delta > 14:
                # Parse time range for (starts) and (ends) events if present
                all_day = True
                start_dt, end_dt = start, end
                if time_str:
                    import re
                    time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)]
                    try:
                        t_start = datetime.strptime(time_parts[0], "%I:%M %p").time()
                        start_dt = start.replace(hour=t_start.hour, minute=t_start.minute)
                        if len(time_parts) > 1 and time_parts[1]:
                            t_end = datetime.strptime(time_parts[1], "%I:%M %p").time()
                            end_dt = end.replace(hour=t_end.hour, minute=t_end.minute)
                        else:
                            end_dt = start_dt
                        all_day = False
                    except Exception:
                        start_dt, end_dt = start, end
                        all_day = True
                events.append({
                    "title": f"{title} (starts)",
                    "date": start_dt.isoformat(),
                    "end": start_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
                events.append({
                    "title": f"{title} (ends)",
                    "date": end_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
            elif delta > 0:
                # Multi-day event, create an event for each day
                import re
                time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)] if time_str else []
                try:
                    t_start = datetime.strptime(time_parts[0], "%I:%M %p").time() if time_parts else None
                    t_end = datetime.strptime(time_parts[1], "%I:%M %p").time() if len(time_parts) > 1 and time_parts[1] else None
                    all_day = False if t_start else True
                except Exception:
                    t_start = t_end = None
                    all_day = True
                for i in range(delta + 1):
                    day = start + timedelta(days=i)
                    if t_start:
                        event_start = day.replace(hour=t_start.hour, minute=t_start.minute)
                        event_end = day.replace(hour=t_end.hour, minute=t_end.minute) if t_end else event_start
                    else:
                        event_start = event_end = day
                    events.append({
                        "title": title,
                        "date": event_start.isoformat(),
                        "end": event_end.isoformat(),
                        "allDay": all_day,
                        "description": desc,
                        "link": url,
                        "color": "#1E90FF",
                        "source": "Downtown Pittsburgh",
                        "categories": categories
                    })
            else:
                # Single-day event (delta == 0)
                all_day = True
                start_dt, end_dt = start, end
                if time_str:
                    import re
                    time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)]
                    try:
                        t_start = datetime.strptime(time_parts[0], "%I:%M %p").time()
                        start_dt = start.replace(hour=t_start.hour, minute=t_start.minute)
                        if len(time_parts) > 1 and time_parts[1]:
                            t_end = datetime.strptime(time_parts[1], "%I:%M %p").time()
                            end_dt = end.replace(hour=t_end.hour, minute=t_end.minute)
                        else:
                            end_dt = start_dt
                        all_day = False
                    except Exception:
                        start_dt, end_dt = start, end
                        all_day = True
                events.append({
                    "title": title,
                    "date": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
        continue
    return events

def scrape_downtown_pittsburgh_events_from_file(html_path):
    with open(html_path, encoding="utf-8") as f:
        soup = BeautifulSoup(f, "html.parser")
    events = []
    for event_card in soup.select("div.copyContent"):
        # Categories
        raw_categories = [t.get_text(strip=True).rstrip(',') for t in event_card.select(".category .term")]
        categories = normalize_categories(raw_categories)
        # Title
        title_tag = event_card.select_one("h1 a")
        title = title_tag.get_text(strip=True) if title_tag else "Untitled Event"
        # URL
        url = title_tag['href'] if title_tag and title_tag.has_attr('href') else ''
        if url and url.startswith('/'):
            url = f"https://downtownpittsburgh.com{url}"
        # Date and time
        eventdate = event_card.select_one(".eventdate")
        date_str, time_str = '', ''
        if eventdate:
            # Robustly extract date and time from eventdate
            eventdate_text = eventdate.get_text(separator="|", strip=True)
            parts = [p.strip() for p in eventdate_text.split('|')]
            date_str = parts[0] if len(parts) > 0 else ''
            time_str = parts[1] if len(parts) > 1 else ''
        # Description
        desc = event_card.get_text(" ", strip=True)
        # Debug print
        print(f"Scraping event: {title}\n  date_str: '{date_str}'\n  time_str: '{time_str}'\n  categories: {categories}")

        # Use robust date parser
        current_year = datetime.now().year
        date_tuple = parse_flexible_date_range(date_str, current_year) if date_str else None
        if date_tuple:
            start, end = date_tuple
            delta = (end - start).days
            if delta > 14:
                # Parse time range for (starts) and (ends) events if present
                all_day = True
                start_dt, end_dt = start, end
                if time_str:
                    import re
                    time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)]
                    try:
                        t_start = datetime.strptime(time_parts[0], "%I:%M %p").time()
                        start_dt = start.replace(hour=t_start.hour, minute=t_start.minute)
                        if len(time_parts) > 1 and time_parts[1]:
                            t_end = datetime.strptime(time_parts[1], "%I:%M %p").time()
                            end_dt = end.replace(hour=t_end.hour, minute=t_end.minute)
                        else:
                            end_dt = start_dt
                        all_day = False
                    except Exception:
                        start_dt, end_dt = start, end
                        all_day = True
                events.append({
                    "title": f"{title} (starts)",
                    "date": start_dt.isoformat(),
                    "end": start_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
                events.append({
                    "title": f"{title} (ends)",
                    "date": end_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
            elif delta > 0:
                # Multi-day event, create an event for each day
                import re
                time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)] if time_str else []
                try:
                    t_start = datetime.strptime(time_parts[0], "%I:%M %p").time() if time_parts else None
                    t_end = datetime.strptime(time_parts[1], "%I:%M %p").time() if len(time_parts) > 1 and time_parts[1] else None
                    all_day = False if t_start else True
                except Exception:
                    t_start = t_end = None
                    all_day = True
                for i in range(delta + 1):
                    day = start + timedelta(days=i)
                    if t_start:
                        event_start = day.replace(hour=t_start.hour, minute=t_start.minute)
                        event_end = day.replace(hour=t_end.hour, minute=t_end.minute) if t_end else event_start
                    else:
                        event_start = event_end = day
                    events.append({
                        "title": title,
                        "date": event_start.isoformat(),
                        "end": event_end.isoformat(),
                        "allDay": all_day,
                        "description": desc,
                        "link": url,
                        "color": "#1E90FF",
                        "source": "Downtown Pittsburgh",
                        "categories": categories
                    })
            else:
                # Single-day event (delta == 0)
                all_day = True
                start_dt, end_dt = start, end
                if time_str:
                    import re
                    time_parts = [t.strip() for t in re.split(r'-|–|—', time_str)]
                    try:
                        t_start = datetime.strptime(time_parts[0], "%I:%M %p").time()
                        start_dt = start.replace(hour=t_start.hour, minute=t_start.minute)
                        if len(time_parts) > 1 and time_parts[1]:
                            t_end = datetime.strptime(time_parts[1], "%I:%M %p").time()
                            end_dt = end.replace(hour=t_end.hour, minute=t_end.minute)
                        else:
                            end_dt = start_dt
                        all_day = False
                    except Exception:
                        start_dt, end_dt = start, end
                        all_day = True
                events.append({
                    "title": title,
                    "date": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "allDay": all_day,
                    "description": desc,
                    "link": url,
                    "color": "#1E90FF",
                    "source": "Downtown Pittsburgh",
                    "categories": categories
                })
        continue
    return events

def save_events_to_db(events, db_path="events.db", source_name="Downtown Pittsburgh"):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("PRAGMA table_info(events)")
    columns = [row[1] for row in c.fetchall()]
    if "genre" not in columns:
        c.execute("ALTER TABLE events ADD COLUMN genre TEXT")

    # Remove old entries from this source for today and later
    today = datetime.today().strftime("%Y-%m-%d")
    c.execute("DELETE FROM events WHERE source = ? AND date >= ?", (source_name, today))
    added = 0
    for event in events:
        # Skip duplicates
        c.execute("SELECT 1 FROM events WHERE title = ? AND date = ? AND source = ?", (event.get("title"), event.get("date"), source_name))
        if c.fetchone():
            continue
        c.execute('''INSERT INTO events (title, date, end, allDay, description, link, color, source, genre)
                     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                  (
                      event.get("title"),
                      event.get("date"),
                      event.get("end"),
                      int(event.get("allDay", False)),
                      event.get("description"),
                      event.get("link"),
                      event.get("color"),
                      source_name,
                    ", ".join(event["categories"]) if isinstance(event.get("categories"), list) else ""

                ))
        added += 1
    conn.commit()
    conn.close()
    print(f"Saved {added} events to {db_path}")

def clear_downtown_pittsburgh_events(db_path="events.db", source_name="Downtown Pittsburgh"):
    """
    Delete all events from the given source from the database.
    """
    conn = sqlite3.connect(db_path)
    c = conn.cursor()
    c.execute("DELETE FROM events WHERE source = ?", (source_name,))
    conn.commit()
    conn.close()
    print(f"Cleared all events from source '{source_name}' in {db_path}")

if __name__ == "__main__":
    clear_downtown_pittsburgh_events(db_path="events.db", source_name="Downtown Pittsburgh")
    events = scrape_downtown_pittsburgh_events()
    save_events_to_db(events, db_path="events.db", source_name="Downtown Pittsburgh")
    for event in events:
        print("[DEBUG] Saving event:", event.get("title"), "| categories:", event.get("categories"))
    print(json.dumps(events, indent=2))
