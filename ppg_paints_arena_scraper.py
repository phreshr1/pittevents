import requests
import sqlite3
from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from multiprocessing import Pool
import time

BASE_URL = "https://www.ppgpaintsarena.com"
LISTING_URL = f"{BASE_URL}/events"
SOURCE = "PPG Paints Arena"
COLOR = "#DC143C"

def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def fetch_main_cards():
    driver = create_driver()
    driver.get(LISTING_URL)
    wait = WebDriverWait(driver, 10)

    # Click "Load More Events" repeatedly until it's gone
    while True:
        try:
            load_more = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, ".load-more button")))
            print("[↻] Clicking 'Load More Events'...")
            driver.execute_script("arguments[0].click();", load_more)
            time.sleep(2)
        except:
            print("[✓] No more 'Load More Events' button.")
            break

    soup = BeautifulSoup(driver.page_source, "html.parser")
    cards = soup.select(".eventItem.entry")
    print(f"[INFO] Found {len(cards)} event cards (after loading all)")
    driver.quit()
    return cards

def parse_main_card(card):
    try:
        title_elem = card.select_one("h3.title a")
        if not title_elem:
            return None

        title = title_elem.get_text(strip=True)
        link = title_elem["href"]
        if not link.startswith("http"):
            link = BASE_URL + link

        return {
            "title": title,
            "link": link
        }
    except Exception as e:
        print(f"[!] Failed to parse card: {e}")
        return None

def extract_showtimes(event):
    try:
        driver = create_driver()
        driver.get(event["link"])
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        driver.quit()
    except Exception as e:
        print(f"[!] Failed to load detail page for {event['title']}: {e}")
        return []

    try:
        showtimes = []
        showing_lis = soup.select("div.event_showings ul.list li")

        print(f"[DEBUG] {event['title']} — Found {len(showing_lis)} <li> blocks in .event_showings")

        for li in showing_lis:
            try:
                month = li.select_one(".m-date__month").get_text(strip=True)
                day = li.select_one(".m-date__day").get_text(strip=True)
                time_str = li.select_one(".time.cell").get_text(strip=True)

                dt = datetime.strptime(f"{month} {day} {time_str}", "%b %d %I:%M %p")
                dt = dt.replace(year=datetime.today().year)

                showtimes.append({
                    "title": event["title"],
                    "date": dt.isoformat(),
                    "end": None,
                    "link": event["link"],
                    "allDay": 0,
                    "description": "",
                    "source": SOURCE,
                    "color": COLOR,
                    "venue": "PPG Paints Arena"
                })
            except Exception as e:
                print(f"[!] Error parsing <li>: {e}")
                continue

        return showtimes
    except Exception as e:
        print(f"[!] Error parsing detail page for {event['title']}: {e}")
        return []


def worker(event):
    return extract_showtimes(event)

def save_events(events):
    conn = sqlite3.connect("events.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(events)")
    columns = [col[1] for col in cursor.fetchall()]
    if "description" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN description TEXT")
    if "genre" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN genre TEXT")
    if "venue" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN venue TEXT")
    if "price" not in columns:
        cursor.execute("ALTER TABLE events ADD COLUMN price TEXT")

    cursor.execute("DELETE FROM events WHERE source = ?", (SOURCE,))
    for e in events:
        cursor.execute("""
            INSERT INTO events (title, date, end, link, allDay, color, source, description, venue)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (e["title"], e["date"], e["end"], e["link"], e["allDay"], e["color"], e["source"], e["description"], e["venue"]))
    conn.commit()
    conn.close()
    print(f"[✓] Saved {len(events)} events to database.")

def run_scraper():
    print("[INFO] Fetching event cards...")
    cards = fetch_main_cards()
    base_events = [parse_main_card(card) for card in cards if card]
    base_events = [e for e in base_events if e]
    print(f"[INFO] Extracting times from {len(base_events)} detail pages...")

    with Pool(processes=4) as pool:
        results = pool.map(worker, base_events)

    all_events = [ev for group in results for ev in group]
    save_events(all_events)

if __name__ == "__main__":
    run_scraper()