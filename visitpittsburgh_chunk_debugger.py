import json
import os
import sqlite3
import time
from datetime import datetime, timedelta
from multiprocessing import Pool
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from dateutil.parser import parse
from math import ceil
import re

CHUNK_SIZE = 50
RESUME_FILE = "visitpittsburgh_resume.json"
BASE_SOURCE = "VisitPittsburgh"
COLOR = "#FFD700"
URL = "https://www.visitpittsburgh.com/events-festivals/?hitsPerPage=400"
OUTPUT_DIR = "json_dumps"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_resume_state():
    if os.path.exists(RESUME_FILE):
        try:
            with open(RESUME_FILE, "r") as f:
                return set(json.load(f).get("done", []))
        except Exception:
            return set()
    return set()

def save_resume_state(done_indices):
    with open(RESUME_FILE, "w") as f:
        json.dump({"done": list(done_indices)}, f)

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def fetch_main_page_cards():
    driver = create_driver()
    driver.set_page_load_timeout(20)
    driver.get(URL)
    time.sleep(3)
    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
    time.sleep(2)
    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    return soup.select(".card__body")

def parse_flexible_date_range(raw_date, current_year):
    try:
        raw_date = raw_date.replace("–", "-").replace("—", "-")
        parts = [p.strip() for p in raw_date.split("-")]
        if len(parts) == 2:
            start = parse(parts[0])
            end = parse(parts[1])
            return start, end
        if len(parts) == 1:
            date = parse(parts[0])
            return date, date
    except Exception as e:
        print(f"[ERROR] Flexible date parse failed: '{raw_date}' -> {e}")
    return None

def extract_event_data(card):
    try:
        title_elem = card.select_one(".card__heading")
        date_elem = card.select_one(".card__date-heading")
        address_block = card.select(".card__address span")
        if not title_elem or not date_elem:
            return None
        title = title_elem.get_text(strip=True)
        raw_date = date_elem.get_text(strip=True)
        year = datetime.now().year
        parsed = parse_flexible_date_range(raw_date, year)
        if not parsed:
            return None
        start_date, end_date = parsed
        link = "https://www.visitpittsburgh.com" + title_elem["href"]
        category = title_elem.get("data-dms-category-name", "Uncategorized").strip()
        address = ", ".join(span.get_text(strip=True) for span in address_block)
        desc = f"Address: {address}"
        return {
            "title": title, "link": link, "description": desc,
            "source": f"{BASE_SOURCE} - {category}",
            "category": category,
            "start_date": start_date, "end_date": end_date
        }
    except Exception as e:
        print(f"[ERROR] extract_event_data failed: {e}")
        return None

def extract_times_from_detail(event):
    print(f"[→] Processing event: {event['title']} ({event['link']})")
    try:
        driver = create_driver()
        driver.set_page_load_timeout(20)
        driver.get(event["link"])
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
    except Exception as e:
        print(f"[ERROR] Failed to load page {event['link']}: {e}")
        return []

    results = []
    all_text = soup.get_text(" ", strip=True)
    fallback_pattern = r"(\d{1,2}:\d{2}\s*[APMapm]{2})\s*(?:to|–|-)\s*(\d{1,2}:\d{2}\s*[APMapm]{2})"
    match = re.search(fallback_pattern, all_text)
    if match:
        start_time, end_time = match.groups()
        current = event["start_date"]
        while current <= event["end_date"]:
            try:
                start_dt = datetime.strptime(f"{current.strftime('%Y-%m-%d')} {start_time}", "%Y-%m-%d %I:%M %p")
                end_dt = datetime.strptime(f"{current.strftime('%Y-%m-%d')} {end_time}", "%Y-%m-%d %I:%M %p")
                results.append({
                    "title": event["title"],
                    "date": start_dt.isoformat(),
                    "end": end_dt.isoformat(),
                    "link": event["link"],
                    "description": event["description"],
                    "source": event["source"],
                    "color": COLOR,
                    "allDay": 0
                })
            except:
                continue
            current += timedelta(days=1)
    return results


def run_safe_worker(event):
    try:
        print(f"[→] START: {event['title']} ({event['link']})")
        result = extract_times_from_detail(event)
        print(f"[✓] DONE: {event['title']}")
        return result
    except Exception as e:
        print(f"[ERROR] Worker failed for {event['title']}: {e}")
        try:
            with open("skipped_events.txt", "a") as skip_log:
                skip_log.write(f"{event['title']}\t{event['link']}\n")
        except:
            pass
        return []

def run_debug_scraper(chunk_index=None):
    cards = fetch_main_page_cards()
    events = [extract_event_data(c) for c in cards if c]
    events = [e for e in events if e]
    print(f"[INFO] Total events: {len(events)}")

    chunks = [events[i:i+CHUNK_SIZE] for i in range(0, len(events), CHUNK_SIZE)]
    if chunk_index is None:
        print(f"[INFO] Available chunks: {len(chunks)}")
        return

    if chunk_index >= len(chunks):
        print(f"[ERROR] Invalid chunk index {chunk_index}")
        return

    chunk = chunks[chunk_index]
    print(f"[INFO] Testing chunk {chunk_index + 1}/{len(chunks)} ({len(chunk)} events)")

    results = []
    for event in chunk:
        results.extend(run_safe_worker(event))

    with open(f"{OUTPUT_DIR}/chunk_debug_{chunk_index + 1}.json", "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"[✓] Saved debug output for chunk {chunk_index + 1}")

if __name__ == "__main__":
    import sys
    idx = int(sys.argv[1]) if len(sys.argv) > 1 else None
    run_debug_scraper(idx)