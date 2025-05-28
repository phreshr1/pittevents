
import sqlite3
import time
from datetime import datetime
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

SOURCE = "Pittsburgh Parks"
COLOR = "#4CAF50"
BASE_URL = "https://pittsburghparks.org/events/month/"

from datetime import datetime

def parse_event_article(article, page_date_hint):
    try:
        title_tag = article.select_one("a.tribe-events-calendar-month__calendar-event-title-link")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        link = title_tag["href"]

        # Traverse upward to find a parent with id="tribe-events-calendar-day-YYYY-MM-DD"
        day_date = None
        parent = article
        while parent:
            parent = parent.find_parent()
            if parent and parent.has_attr("id") and parent["id"].startswith("tribe-events-calendar-day-"):
                day_date = parent["id"].replace("tribe-events-calendar-day-", "")
                break

        if not day_date:
            print(f"[!] Could not determine date for: {title}")
            return None

        # Extract times
        time_tags = article.select("time")
        start_time = time_tags[0].get("datetime", "").strip() if time_tags else "00:00"
        end_time = time_tags[1].get("datetime", "").strip() if len(time_tags) > 1 else None

        # Construct full datetime strings
        full_start = f"{day_date}T{start_time}" if ":" in start_time else f"{day_date}T00:00:00"
        full_end = f"{day_date}T{end_time}" if end_time and ":" in end_time else None

        print(f"[✓] Event: {title}")
        print(f"    Date:  {day_date}")
        print(f"    Start: {full_start}")
        if full_end:
            print(f"    End:   {full_end}")

        return {
            "title": title,
            "date": full_start,
            "end": full_end,
            "link": link,
            "description": ""
        }

    except Exception as e:
        print(f"[!] Parse error: {e}")
        return None



# Set up browser
options = Options()
options.add_argument("--headless")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
driver = webdriver.Chrome(options=options)
driver.get(BASE_URL)
time.sleep(3)

events = []

for i in range(12):
    print(f"[INFO] Scraping month {i+1}/12...")
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "article.tribe-events-calendar-month__calendar-event"))
        )
    except Exception:
        print("[WARNING] No events visible for this month.")
        continue

    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Extract the month/year label to use as a fallback date
    label = soup.select_one("h2.tribe-events-c-top-bar__title")
    page_date_hint = label.get_text(strip=True).replace("Events for", "").strip() if label else datetime.today().strftime("%B %Y")

    articles = soup.select("article.tribe-events-calendar-month__calendar-event")
    print(f"[DEBUG] Found {len(articles)} event articles.")
    for article in articles:
        event = parse_event_article(article, page_date_hint)
        if event:
            events.append(event)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a.tribe-events-c-nav__next"))
        )
        next_button = driver.find_element(By.CSS_SELECTOR, "a.tribe-events-c-nav__next")
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", next_button)
        time.sleep(1)
        driver.execute_script("arguments[0].click();", next_button)
        print("[DEBUG] Clicked 'Next'.")
        time.sleep(2)
    except Exception as e:
        print(f"[INFO] No more 'Next' button or click failed — exiting loop after {i+1} months.")
        break

driver.quit()

# Save to SQLite
print(f"[INFO] Saving {len(events)} events to database...")
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
# Deduplicate by (title, date)
seen = set()
unique_events = []
for e in events:
    key = (e["title"], e["date"])
    if key not in seen:
        seen.add(key)
        unique_events.append(e)

print(f"[INFO] Deduplicated from {len(events)} to {len(unique_events)} events.")

# Insert only unique events
for e in unique_events:
    cursor.execute("""
        INSERT INTO events (title, date, end, link, allDay, color, source, description)
        VALUES (?, ?, ?, ?, 0, ?, ?, ?)
    """, (
        e["title"], e["date"], e["end"], e["link"], COLOR, SOURCE, e["description"]
    ))

conn.commit()
conn.close()
print(f"[✓] Loaded {len(events)} events from {SOURCE}.")
