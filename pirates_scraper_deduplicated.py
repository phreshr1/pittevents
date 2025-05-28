import requests
import sqlite3
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
import time
from pytz import timezone, utc

TEAM_ID = 134  # Pittsburgh Pirates
SEASON = 2025
API_URL = f"https://statsapi.mlb.com/api/v1/schedule?sportId=1&teamId={TEAM_ID}&season={SEASON}&gameType=R"

# --------- Scrape special events from live site using Selenium ---------
def scrape_special_events_live():
    events_by_date = {}
    try:
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        options.add_argument("--no-sandbox")
        options.add_argument("--window-size=1920,1080")

        driver = webdriver.Chrome(options=options)
        driver.get("https://www.mlb.com/pirates/tickets/single-game-tickets")
        time.sleep(5)  # Wait for dynamic content to load

        eventboxes = driver.find_elements(By.CSS_SELECTOR, '[data-testid="eventbox"]')
        for box in eventboxes:
            try:
                date_iso = box.get_attribute("data-date")
                dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                date_key = dt.strftime("%Y-%m-%d")

                titles = box.find_elements(By.CSS_SELECTOR, "p[class^='styles__PromotionOfferName']")
                specials = [
                    t.text.strip()
                    for t in titles
                    if t.text.strip() and "group tickets" not in t.text.strip().lower()
                ]
                if specials:
                    events_by_date.setdefault(date_key, []).extend(specials)
            except Exception:
                continue

        driver.quit()
        print(f"[\u2713] Scraped {sum(len(v) for v in events_by_date.values())} special events from live site.")
    except Exception as e:
        print(f"[!] Failed to scrape live: {e}")
    return events_by_date

# --------- Fallback: Load special events from saved HTML ---------
def load_special_events_from_html(path="Buy Pirates Tickets _ Pittsburgh Pirates.html"):
    events_by_date = {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            soup = BeautifulSoup(f, "html.parser")
            game_boxes = soup.select('[data-testid="eventbox"]')

            for box in game_boxes:
                date_iso = box.get("data-date")
                if not date_iso:
                    continue
                try:
                    dt = datetime.fromisoformat(date_iso.replace("Z", "+00:00"))
                    date_key = dt.strftime("%Y-%m-%d")
                except Exception:
                    continue

                titles = [
                    p.get_text(strip=True)
                    for p in box.select("p[class^='styles__PromotionOfferName']")
                    if "group tickets" not in p.get_text(strip=True).lower()
                ]
                if titles:
                    events_by_date.setdefault(date_key, []).extend(titles)

        print(f"[\u2713] Parsed {sum(len(v) for v in events_by_date.values())} special events from backup HTML.")
    except Exception as e:
        print(f"[!] Failed to load special events from fallback HTML: {e}")
    return events_by_date

# --------- Load special events ---------
special_events = scrape_special_events_live()
if not special_events:
    special_events = load_special_events_from_html()

# --------- Load basic games from MLB API ---------
response = requests.get(API_URL)
data = response.json()

events = []
eastern = timezone("US/Eastern")
for date in data.get("dates", []):
    for game in date.get("games", []):
        game_date = game.get("gameDate")
        venue = game.get("venue", {}).get("name")
        home_team = game.get("teams", {}).get("home", {}).get("team", {}).get("name")
        away_team = game.get("teams", {}).get("away", {}).get("team", {}).get("name")
        if home_team != "Pittsburgh Pirates":
            continue

        try:
            utc_dt = datetime.fromisoformat(game_date.replace("Z", "+00:00"))
            dt = utc_dt.astimezone(eastern)
            start = dt.strftime("%Y-%m-%dT%H:%M:%S")
            short_date = dt.strftime("%Y-%m-%d")
        except Exception:
            continue

        base_title = f"{away_team} @ Pittsburgh Pirates"
        specials = special_events.get(short_date, [])
        if specials:
            unique_specials = list(dict.fromkeys(specials))  # preserves order, removes duplicates
            special_str = " | ".join(unique_specials)
            title = f"{base_title} | {special_str}"
            description = ", ".join(specials)
        else:
            title = base_title
            description = ""

        events.append({
            "title": title,
            "date": start,
            "link": "https://www.mlb.com/pirates/tickets/single-game-tickets",
            "venue": venue,
            "description": description
        })

# --------- Insert into SQLite database ---------
conn = sqlite3.connect("events.db")
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(events)")
columns = [row[1] for row in cursor.fetchall()]
if "description" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN description TEXT")
if "genre" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN genre TEXT")
if "venue" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN venue TEXT")
if "price" not in columns:
    cursor.execute("ALTER TABLE events ADD COLUMN price TEXT")

cursor.execute("DELETE FROM events WHERE source = 'Pirates'")

for e in events:
    cursor.execute("""
        INSERT INTO events (title, date, end, link, allDay, color, source, description, venue)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        e["title"], e["date"], None, e["link"], 0,
        "#000000", "Pirates", e["description"], e["venue"]
    ))

conn.commit()
conn.close()

print(f"[\u2713] Loaded {len(events)} Pirates games into database.")
