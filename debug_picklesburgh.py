from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import time
import re

URL = "https://www.visitpittsburgh.com/events-festivals/?hitsPerPage=400"
def create_driver():
    options = Options()
    options.add_argument("--headless")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1920,1080")
    return webdriver.Chrome(options=options)

def fetch_all_event_cards():
    driver = create_driver()
    driver.get(URL)
    time.sleep(3)

    # Repeatedly click "Show More" button
    for _ in range(40):
        try:
            button = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ais-InfiniteHits-loadMore"))
            )
            if not button.is_displayed() or "disabled" in button.get_attribute("class"):
                break
            prev_count = len(driver.find_elements(By.CLASS_NAME, "card__body"))
            driver.execute_script("arguments[0].click();", button)
            time.sleep(2)
            WebDriverWait(driver, 10).until(
                lambda d: len(d.find_elements(By.CLASS_NAME, "card__body")) > prev_count
            )
        except:
            break

    soup = BeautifulSoup(driver.page_source, "html.parser")
    driver.quit()
    return soup.select(".card__body")

def parse_card(card):
    title_elem = card.select_one(".card__heading")
    date_elem = card.select_one(".card__date-heading")

    if not title_elem or not date_elem:
        return None

    title = title_elem.get_text(strip=True)
    link = "https://www.visitpittsburgh.com" + title_elem["href"]
    raw_date = date_elem.get_text(strip=True).replace("–", "-").replace("—", "-").strip()

    return {"title": title, "link": link, "raw_date": raw_date}

def extract_times_from_detail(url):
    driver = create_driver()
    try:
        driver.get(url)
        time.sleep(2)
        soup = BeautifulSoup(driver.page_source, "html.parser")
        all_text = soup.get_text(" ", strip=True)
        print(f"\n[DETAIL PAGE CONTENT]\n{all_text[:1000]}...\n")

        discrete_pattern = r"(\w{3} \d{1,2}, \d{4}),\s*(\d{1,2}:\d{2}[ap]m)\s*to\s*(\d{1,2}:\d{2}[ap]m)"
        fallback_pattern = r"(\d{1,2}:\d{2}\s*[APMapm]{2})\s*(?:to|–|-)\s*(\d{1,2}:\d{2}\s*[APMapm]{2})"

        matches = re.findall(discrete_pattern, all_text)
        if matches:
            print("[✓] Found discrete times:")
            for m in matches:
                print("  ", m)
            return

        match = re.search(fallback_pattern, all_text)
        if match:
            print("[✓] Found fallback time range:", match.groups())
        else:
            print("[!] No recognizable time formats found.")
    finally:
        driver.quit()

def main():
    cards = fetch_all_event_cards()
    print(f"[INFO] Found {len(cards)} cards total")

    for card in cards:
        data = parse_card(card)
        if data and "picklesburgh" in data["title"].lower():
            print("\n[✓] FOUND PICKLESBURGH\n")
            print(f"Title: {data['title']}")
            print(f"Link: {data['link']}")
            print(f"Raw Date: {data['raw_date']}")

            try:
                parts = [p.strip() for p in data['raw_date'].split("-")]
                year = datetime.now().year
                if len(parts) == 2:
                    start = datetime.strptime(f"{parts[0]} {year}", "%b %d %Y")
                    end = datetime.strptime(f"{parts[1]} {year}", "%b %d %Y")
                    print(f"Parsed Start: {start} | End: {end}")
                elif len(parts) == 1:
                    start = datetime.strptime(f"{parts[0]} {year}", "%b %d %Y")
                    print(f"Parsed Single Date: {start}")
                else:
                    print("[!] Failed to parse date.")
            except Exception as e:
                print("[!] Date parsing error:", e)

            extract_times_from_detail(data["link"])
            return

    print("[!] Picklesburgh event not found in any card.")

if __name__ == "__main__":
    main()