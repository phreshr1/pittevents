
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import sqlite3
import time
import re
import multiprocessing as mp

BASE_SOURCE = "VisitPittsburgh"
COLOR = "#FFD700"
URL = "https://www.visitpittsburgh.com/events-festivals/?hitsPerPage=400"

discrete_pattern = r"(\w{3} \d{1,2}, \d{4}),\s*(\d{1,2}:\d{2}[ap]m)\s*to\s*(\d{1,2}:\d{2}[ap]m)"
fallback_pattern = r"(\d{1,2}:\d{2}\s*[APMapm]{2})\s*(?:to|–|-)\s*(\d{1,2}:\d{2}\s*[APMapm]{2})"

def parse_flexible_date_range(raw_date: str, current_year: int) -> tuple[datetime, datetime] | None:
    """
    Parses date strings like 'May 28 - Sep 11' or 'May 28, 2025 - Mar 29 2026'.
    Returns a tuple of (start_date, end_date) or None if parsing fails.
    """
    try:
        raw_date = raw_date.replace("–", "-").replace("—", "-")
        parts = [p.strip() for p in raw_date.split("-")]

        # Format: 'May 28 - Sep 11'
        if len(parts) == 2 and re.match(r"^[A-Za-z]{3}", parts[0]) and re.match(r"^[A-Za-z]{3}", parts[1]):
            start = datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")
            end = datetime.strptime(f"{parts[1]} {current_year}", "%b %d %Y")
            if end < start:
                end = end.replace(year=end.year + 1)
            return start, end

        # Format: 'May 28 - 31' (assumes same month)
        if len(parts) == 2 and re.match(r"^[A-Za-z]{3}", parts[0]) and parts[1].isdigit():
            base = datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")
            end = base.replace(day=int(parts[1]))
            if end < base:
                end = end.replace(year=end.year + 1)
            return base, end

        # Format: 'May 28, 2025 - Jan 1 2026'
        if len(parts) == 2 and ("," in parts[0] or any(char.isdigit() for char in parts[1])):
            try:
                start = datetime.strptime(parts[0], "%b %d, %Y")
                end = datetime.strptime(parts[1], "%b %d %Y")
                return start, end
            except ValueError:
                pass

        # Format: 'May 28' or 'May 28, 2025'
        try:
            return datetime.strptime(parts[0], "%b %d, %Y"), datetime.strptime(parts[0], "%b %d, %Y")
        except:
            return datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y"), datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")

    except Exception as e:
        print(f"[ERROR] Flexible date parse failed: '{raw_date}' -> {e}")
        return None

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def extract_times_from_detail(url, start_date=None, end_date=None, category=None, title=None):
    driver = create_driver()
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_text = soup.get_text(" ", strip=True)

        entries = []
        section = soup.find(string=re.compile("Happens on the following Dates", re.I))
        if section:
            tag = section.find_parent()
            while tag:
                tag = tag.find_next_sibling()
                if tag and tag.name in ["p", "div", "li"]:
                    text = tag.get_text(strip=True)
                    match = re.search(discrete_pattern, text)
                    if match:
                        date_str, start_str, end_str = match.groups()
                        try:
                            start_dt = datetime.strptime(f"{date_str} {start_str}", "%b %d, %Y %I:%M%p")
                            end_dt = datetime.strptime(f"{date_str} {end_str}", "%b %d, %Y %I:%M%p")
                            entries.append((start_dt, end_dt))
                        except ValueError:
                            continue
                else:
                    break
        if entries:
            return entries, None

        if start_date and end_date and (end_date - start_date).days > 14:
            return [
                (start_date.replace(hour=8), start_date.replace(hour=10)),
                (end_date.replace(hour=8), end_date.replace(hour=10))
            ], "exhibit"

        if start_date and end_date:
            match = re.search(fallback_pattern, all_text)
            if match:
                start_time, end_time = match.groups()
                results = []
                current = start_date
                while current <= end_date:
                    try:
                        start_dt = datetime.strptime(f"{current.strftime('%Y-%m-%d')} {start_time}", "%Y-%m-%d %I:%M %p")
                        end_dt = datetime.strptime(f"{current.strftime('%Y-%m-%d')} {end_time}", "%Y-%m-%d %I:%M %p")
                        results.append((start_dt, end_dt))
                    except:
                        continue
                    current += timedelta(days=1)
                return results, None

        return [], None
    finally:
        driver.quit()

from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By

def fetch_main_page_cards():
    driver = create_driver()
    driver.get(URL)
    time.sleep(3)

    # Single scroll to trigger any lazy loading
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)

    cards = driver.find_elements(By.CLASS_NAME, "card__body")
    print(f"[INFO] Found {len(cards)} event cards")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    return soup.select(".card__body")

from dateutil.parser import parse

def extract_event_data(card):
    try:
        title_elem = card.select_one(".card__heading")
        date_elem = card.select_one(".card__date-heading")
        address_block = card.select(".card__address span")

        if not title_elem or not date_elem:
            return None

        category_raw = title_elem.get("data-dms-category-name")
        category = category_raw.strip() if category_raw else "Uncategorized"
        source = f"{BASE_SOURCE} - {category}"
        title = title_elem.get_text(strip=True)
        link = "https://www.visitpittsburgh.com" + title_elem["href"]
        raw_date = date_elem.get_text(strip=True).replace("–", "-").replace("—", "-").strip()
        address = ", ".join(span.get_text(strip=True) for span in address_block)
        desc = f"Address: {address}"

        parts = [p.strip() for p in raw_date.split("-")]
        year = datetime.now().year

        if len(parts) == 1:
            try:
                start_date = end_date = datetime.strptime(parts[0], "%b %d, %Y")
            except ValueError:
                try:
                    start_date = end_date = datetime.strptime(f"{parts[0]} {year}", "%b %d %Y")
                except Exception:
                    print(f"[ERROR] Failed to parse card: {raw_date}")
                    return None
        elif len(parts) == 2:
            try:
                start_date = parse(parts[0])
                end_date = parse(parts[1])
            except Exception as e:
                print(f"[ERROR] Flexible date parse failed: '{raw_date}' -> {e}")
                print(f"[ERROR] Failed to parse card: {raw_date}")
                return None
        else:
            print(f"[ERROR] Unexpected date format: {raw_date}")
            return None

        return {
            "title": title,
            "link": link,
            "description": desc,
            "source": source,
            "category": category,
            "start_date": start_date,
            "end_date": end_date
        }
    except Exception as e:
        print(f"[ERROR] extract_event_data failed: {e}")
        return None

def worker(event):
    times, exhibit_flag = extract_times_from_detail(
        event["link"],
        event["start_date"],
        event["end_date"],
        event["category"],
        event["title"]
    )
    
    result = []
    for idx, (start_dt, end_dt) in enumerate(times):
        title = event["title"]

        if exhibit_flag == "exhibit":
            if idx == 0:
                title = f"{title} (Begins)"
            elif idx == len(times) - 1:
                title = f"{title} (Ends)"
            result.append({
                "title": title,
                "date": start_dt.date().isoformat(),
                "end": None,
                "link": event["link"],
                "description": event["description"],
                "source": event["source"],
                "color": COLOR,
                "allDay": 1
            })
        else:
            result.append({
                "title": title,
                "date": start_dt.isoformat(),
                "end": end_dt.isoformat() if end_dt else None,
                "link": event["link"],
                "description": event["description"],
                "source": event["source"],
                "color": COLOR,
                "allDay": 0
            })
    
    return result or []

from math import ceil

def run_scraper(test_mode=True):
    print("[INFO] Fetching main cards...")
    cards = fetch_main_page_cards()
    base_events = [extract_event_data(card) for card in cards[:5] if card] if test_mode else [extract_event_data(card) for card in cards if card]
    base_events = [e for e in base_events if e]

    print(f"[INFO] Extracting event times from {len(base_events)} detail pages...")

    chunk_size = 50
    num_chunks = ceil(len(base_events) / chunk_size)

    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()

    # Clear old VisitPittsburgh events only once
    cursor.execute("DELETE FROM events WHERE source LIKE 'VisitPittsburgh%'")
    conn.commit()

    with mp.Pool(processes=3) as pool:
        for i in range(num_chunks):
            chunk = base_events[i * chunk_size:(i + 1) * chunk_size]
            print(f"[INFO] Processing chunk {i + 1}/{num_chunks} ({len(chunk)} events)...")

            try:
                result = pool.map(worker, chunk)
            except Exception as e:
                print(f"[ERROR] Chunk {i + 1} failed: {e}")
                continue

            flat_events = [item for group in result if group for item in group]

            for e in flat_events:
                cursor.execute("""
                    INSERT INTO events (title, date, end, link, allDay, color, source, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    e["title"], e["date"], e["end"], e["link"], e["allDay"], e["color"], e["source"], e["description"]
                ))
            conn.commit()
            print(f"[✓] Chunk {i + 1} inserted {len(flat_events)} events.")

    conn.close()
    print(f"[✓] Loaded VisitPittsburgh events{' (TEST MODE)' if test_mode else ''}.")

if __name__ == "__main__":
    run_scraper(test_mode=False)
