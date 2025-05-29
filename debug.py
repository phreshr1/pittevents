import json
from datetime import datetime
from pathlib import Path

CHUNK_SIZE = 50
INPUT_FILE = "json_dumps/picklesburgh_events.json"

def load_events():
    with open(INPUT_FILE, "r") as f:
        return json.load(f)

def chunk_events(events, chunk_size):
    return [events[i:i + chunk_size] for i in range(0, len(events), chunk_size)]

def main():
    events = load_events()
    print(f"[INFO] Loaded {len(events)} events.")

    chunks = chunk_events(events, CHUNK_SIZE)

    # 🔍 Find which chunk contains Picklesburgh
    for i, chunk in enumerate(chunks):
        for event in chunk:
            if "picklesburgh" in event["title"].lower():
                print(f"[🎯] Picklesburgh found in chunk {i}")
                break  # optional: stop after first find

    print(f"[INFO] Total chunks: {len(chunks)}")

if __name__ == "__main__":
    main()
