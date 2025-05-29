
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from date_parser_hybrid import parse_flexible_date_range
import sqlite3
import time
import re
import multiprocessing as mp
import json
import os
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import multiprocess as mp

CHUNK_SIZE = 50
RESUME_FILE = "visitpittsburgh_resume.json"
BASE_SOURCE = "VisitPittsburgh"
COLOR = "#FFD700"
URL = "https://www.visitpittsburgh.com/events-festivals/?hitsPerPage=400"

discrete_pattern = r"(\w{3} \d{1,2}, \d{4}),\s*(\d{1,2}:\d{2}[ap]m)\s*to\s*(\d{1,2}:\d{2}[ap]m)"
fallback_pattern = r"(\d{1,2}:\d{2}\s*[APMapm]{2})\s*(?:to|–|-)\s*(\d{1,2}:\d{2}\s*[APMapm]{2})"

def safe_extract_target(q, event):
    try:
        from visitpittsburgh_scraper_true_allday import extract_times_from_detail
        result = extract_times_from_detail(
            event["link"],
            event["start_date"],
            event["end_date"],
            event["category"],
            event["title"]
        )
        q.put(result)
    except Exception:
        q.put(([], None))

def safe_extract(event, timeout=20):
    from multiprocessing import Process, Queue

    q = Queue()
    p = Process(target=safe_extract_target, args=(q, event))
    p.start()
    p.join(timeout)

    if p.is_alive():
        print(f"[⛔] Timeout — killing hung event: {event['title']}")
        p.terminate()
        p.join()
        return [], None

    return q.get() if not q.empty() else ([], None)

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

from selenium.common.exceptions import TimeoutException, WebDriverException

def extract_times_from_detail(url, start_date=None, end_date=None, category=None, title=None):
    print(f"[→] Processing event: {title} ({url})")

    try:
        driver = create_driver()
        driver.set_page_load_timeout(10)

        try:
            driver.get(url)
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            soup = BeautifulSoup(driver.page_source, "html.parser")
            all_text = soup.get_text(" ", strip=True)
            driver.quit()
        except TimeoutException:
            print(f"[⏱️] Timeout while waiting for page to load: {url}")
            driver.quit()
            raise

    except Exception as e:
        print(f"[❌] Selenium failed for {title} → {e}")
        print("[🌐] Trying requests fallback...")

        try:
            import requests
            headers = {"User-Agent": "Mozilla/5.0"}
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            all_text = soup.get_text(" ", strip=True)
        except Exception as e2:
            print(f"[⚠️] Unable to load usable content for: {title}")
            print(f"[💤] Skipping: probably a JavaScript-only or protected page.")
            try:
                with open("skipped_events.txt", "a", encoding="utf-8") as log:
                    log.write(f"{title}\t{url}\n")
            except Exception as log_err:
                print(f"[📝] Could not write to skipped_events.txt: {log_err}")
            return [], None
        except:
            pass
        return [], None

    # Try parsing discrete repeat entries first
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

    # Exhibit fallback
    if start_date and end_date and (end_date - start_date).days > 14:
        return [
            (start_date.replace(hour=8), start_date.replace(hour=10)),
            (end_date.replace(hour=8), end_date.replace(hour=10))
        ], "exhibit"

    # Time fallback
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

    # If nothing matched, return as all-day events
    if start_date and end_date:
        print(f"[🧪] Fallback triggered: start={start_date}, end={end_date}")
        results = []
        current = start_date
        while current <= end_date:
            results.append((current, None))  # None signals all-day
            current += timedelta(days=1)
        return results, None
    print(f"[💥] No fallback possible — start={start_date}, end={end_date}")
    return [], None

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
            parsed = parse_flexible_date_range(raw_date, year)
            if parsed is None:
                print(f"[ERROR] Failed to parse flexible range: {raw_date}")
                return None
            if parsed[1] < parsed[0]:
                print(f"[❌] Invalid date range: start={parsed[0]}, end={parsed[1]} — Skipping '{title}'")
                return None
            start_date, end_date = parsed
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
    times, exhibit_flag = safe_extract(event)

    if not times:
        print(f"[⚠️] SKIPPING {event['title']} — no usable times.")
        try:
            with open("skipped_events.txt", "a", encoding="utf-8") as log:
                log.write(f"{event['title']}\t{event['link']}\n")
        except Exception as log_err:
            print(f"[📝] Could not write to skipped_events.txt: {log_err}")
        return []

    print(f"[👀] {event['title']} → times={times}, exhibit_flag={exhibit_flag}")
    result = []
    for idx, (start_dt, end_dt) in enumerate(times):
        title = event["title"]

        if exhibit_flag == "exhibit":
            if idx == 0:
                title = f"{title} (Begins)"
            elif idx == len(times) - 1:
                title = f"{title} (Ends)"
            print(f"[🧪] INSERTING EXHIBIT: {title} | {start_dt.date()} | allDay=1")
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
            print(f"[🧪] INSERTING: {title} | {start_dt} → {end_dt} | allDay={1 if end_dt is None else 0}")
            result.append({
                "title": title,
                "date": start_dt.date().isoformat() if end_dt is None else start_dt.isoformat(),
                "end": None if end_dt is None else end_dt.isoformat(),
                "link": event["link"],
                "description": event["description"],
                "source": event["source"],
                "color": COLOR,
                "allDay": 1 if end_dt is None else 0
            })

    return result

from math import ceil

def save_resume_state(done_indices):
    with open("json_dumps/resume_state.json", "w") as f:
        json.dump({"done": list(done_indices)}, f)

def load_resume_state():
    if os.path.exists(RESUME_FILE):
        try:
            with open(RESUME_FILE, "r") as f:
                return set(json.load(f).get("done", []))
        except Exception:
            return set()
    return set()
    
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

    done_chunks = load_resume_state()
    print(f"[INFO] Resume mode: Skipping chunks {sorted(done_chunks)}")

    with mp.Pool(processes=3) as pool:
        for i in range(num_chunks):
            if i in done_chunks:
                print(f"[✓] Skipping already completed chunk {i + 1}/{num_chunks}")
                continue

            chunk = base_events[i * chunk_size:(i + 1) * chunk_size]
            print(f"[INFO] Processing chunk {i + 1}/{num_chunks} ({len(chunk)} events)...")

            try:
                result = pool.map(worker, chunk)
            except Exception as e:
                print(f"[ERROR] Chunk {i + 1} failed: {e}")
                continue

            flat_events = [item for group in result if group for item in group]

            # Save chunk to JSON for crash recovery
            os.makedirs("json_dumps", exist_ok=True)
            with open(f"json_dumps/chunk_{i + 1}.json", "w", encoding="utf-8") as f:
                json.dump(flat_events, f, indent=2, default=str)

            for e in flat_events:
                cursor.execute("""
                    INSERT INTO events (title, date, end, link, allDay, color, source, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    e["title"], e["date"], e["end"], e["link"], e["allDay"], e["color"], e["source"], e["description"]
                ))
            conn.commit()

            # Mark chunk as completed
            done_chunks.add(i)
            save_resume_state(done_chunks)

            print(f"[✓] Chunk {i + 1} inserted {len(flat_events)} events.")

if __name__ == "__main__":
    run_scraper(test_mode=False)
