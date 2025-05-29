from visitpittsburgh_scraper_true_allday import fetch_main_page_cards, extract_event_data, CHUNK_SIZE

def find_picklesburgh_chunk():
    print("[INFO] Fetching main cards...")
    cards = fetch_main_page_cards()
    base_events = [extract_event_data(card) for card in cards if card]
    base_events = [e for e in base_events if e]

    chunks = [base_events[i:i + CHUNK_SIZE] for i in range(0, len(base_events), CHUNK_SIZE)]

    for i, chunk in enumerate(chunks):
        for event in chunk:
            if "picklesburgh" in event["title"].lower():
                print(f"[🎯] Found 'Picklesburgh' in chunk {i} (chunk {i+1} of {len(chunks)})")
                return
    print("[❌] Picklesburgh not found in any chunk.")

if __name__ == "__main__":
    find_picklesburgh_chunk()
