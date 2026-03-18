from datetime import datetime


def parse_date(date_str, fmt='%Y-%m-%d'):
    """Parse a date string and return a date object, or None on failure."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, fmt).date()
    except (ValueError, TypeError):
        return None
