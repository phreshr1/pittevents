import sqlite3

DB_PATH = "events.db"
TARGET_DATE = "2025-05-29"
KEYWORD = "(Begins)"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Perform the deletion
cursor.execute("""
    DELETE FROM events
    WHERE title LIKE ?
      AND date LIKE ?
""", (f"%{KEYWORD}%", f"{TARGET_DATE}%"))

deleted_count = cursor.rowcount
conn.commit()
conn.close()

print(f"[✓] Deleted {deleted_count} events with '(Begins)' on {TARGET_DATE}.")
