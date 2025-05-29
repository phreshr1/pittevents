
from visitpittsburgh_scraper_true_allday import create_driver, fetch_main_page_cards, extract_event_data, extract_times_from_detail
from bs4 import BeautifulSoup
import time

TARGET_TITLES = [
    "Picklesburgh 2025",
    "Whose Brine Is It Anyway?",
    "Bravo Academy - Summer Camp week 2"
]

driver = create_driver()
cards = fetch_main_page_cards()

for card in cards:
    data = extract_event_data(card)
    if data and data["title"] in TARGET_TITLES:
        print("\n" + "="*60)
        print(f"[🎯] Found target event: {data['title']}")
        print(f"URL: {data['link']}")
        print(f"Start: {data['start_date']}, End: {data['end_date']}")
        print("[HTML Preview]")
        print(card.get_attribute("outerHTML")[:1000] + "...")

        try:
            print("[→] Loading detail page...")
            driver.get(data["link"])
            time.sleep(2)
            soup = BeautifulSoup(driver.page_source, "html.parser")
            full_text = soup.get_text(" ", strip=True)
            print("[📝] First 500 chars of detail text:")
            print(full_text[:500])
        except Exception as e:
            print(f"[❌] Detail page load error: {e}")
            continue

        print("[→] Extracting times...")
        times, flag = extract_times_from_detail(
            data["link"],
            data["start_date"],
            data["end_date"],
            data["source"],
            data["title"]
        )

        if not times:
            print("[❌] No times returned from detail extraction.")
        else:
            for s, e in times:
                print(f"[✓] Parsed time range: {s} to {e} | All-day: {e is None}")
driver.quit()
