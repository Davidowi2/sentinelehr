from datetime import datetime, timedelta

# EPIC_EPOCH is December 31, 1840
EPIC_EPOCH = datetime(1840, 12, 31)

def to_epic_date(dt: datetime) -> int:
    """Convert Python datetime to Epic internal date integer."""
    return (dt.date() - EPIC_EPOCH.date()).days

def from_epic_date(epic_int: int) -> datetime:
    """Convert Epic internal date integer to Python datetime."""
    return EPIC_EPOCH + timedelta(days=epic_int)

def to_epic_datetime(dt: datetime) -> float:
    """
    Epic stores datetimes as decimal: integer part = date, decimal part = fraction of day (time).
    Example: 67234.5 = day 67234 at noon exactly.
    """
    date_part = to_epic_date(dt)
    time_fraction = (dt.hour * 3600 + dt.minute * 60 + dt.second) / 86400.0
    return round(date_part + time_fraction, 6)

def from_epic_datetime(epic_float: float) -> datetime:
    """Convert Epic datetime float back to Python datetime."""
    date_part = int(epic_float)
    time_fraction = epic_float - date_part
    base_date = from_epic_date(date_part)
    total_seconds = int(time_fraction * 86400)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    return base_date.replace(hour=hours, minute=minutes, second=seconds)
