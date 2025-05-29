from datetime import datetime
from dateutil.parser import parse
import re

def parse_flexible_date_range(raw_date: str, current_year: int) -> tuple[datetime, datetime] | None:
    """
    Hybrid parser: tries robust dateutil parsing first, then custom fallback for formats like:
      - 'May 28 - Sep 11'
      - 'May 28 - 31'
      - 'May 28, 2025 - Jan 1 2026'
      - 'May 28'
    Returns a (start_date, end_date) tuple or None on failure.
    """
    try:
        raw_date = raw_date.replace("–", "-").replace("—", "-")
        parts = [p.strip() for p in raw_date.split("-")]

        # Same-month partial date range: Jul 11 - 13
        if len(parts) == 2 and re.match(r"^[A-Za-z]{3}", parts[0]) and re.match(r"^\d{1,2}$", parts[1]):
            try:
                base = datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")
                end_day = int(parts[1])
                end = base.replace(day=end_day)
                return base, end
            except ValueError as e:
                print(f"[ERROR] Same-month partial range failed: '{raw_date}' -> {e}")
                return None

        # Try dateutil parser first for all formats
        if len(parts) == 2:
            try:
                start = parse(parts[0])
                end = parse(parts[1])
                return start, end
            except:
                pass

        if len(parts) == 1:
            try:
                date = parse(parts[0])
                return date, date
            except:
                pass

        # Fallback for 'May 28 - Sep 11'
        if len(parts) == 2 and re.match(r"^[A-Za-z]{3}", parts[0]) and re.match(r"^[A-Za-z]{3}", parts[1]):
            try:
                start = datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")
                end = datetime.strptime(f"{parts[1]} {current_year}", "%b %d %Y")
                if end < start:
                    end = end.replace(year=end.year + 1)
                return start, end
            except:
                pass

        # Fallback for single date with no year
        if len(parts) == 1:
            try:
                base = datetime.strptime(f"{parts[0]} {current_year}", "%b %d %Y")
                return base, base
            except:
                pass

        print(f"[ERROR] Could not parse date range: '{raw_date}'")
        return None

    except Exception as e:
        print(f"[ERROR] Exception in flexible date parse: '{raw_date}' -> {e}")
        return None
