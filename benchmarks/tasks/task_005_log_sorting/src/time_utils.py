"""Timestamp parsing utilities."""

from datetime import datetime


def parse_timestamp(raw: str) -> datetime:
    """Parse an ISO-8601 timestamp string into a datetime.

    Supports formats like:
        2024-06-01T10:00:00-04:00
        2024-06-01T14:30:00+02:00
        2024-06-01T12:00:00Z

    .. note::
        BUG — the current implementation strips the timezone offset and
        returns a **naive** datetime.  This causes incorrect comparisons
        when timestamps originate from different timezones.
    """
    # Strip timezone suffix to avoid parsing issues (WRONG approach)
    cleaned = raw
    if cleaned.endswith("Z"):
        cleaned = cleaned[:-1]
    elif "+" in cleaned[10:]:
        cleaned = cleaned[: cleaned.rindex("+")]
    elif cleaned.count("-") > 2:
        # has a negative offset like -04:00
        cleaned = cleaned[: cleaned.rindex("-")]

    return datetime.strptime(cleaned, "%Y-%m-%dT%H:%M:%S")
