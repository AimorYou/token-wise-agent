"""Parse raw log lines into structured records."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .time_utils import parse_timestamp


@dataclass
class LogEntry:
    """A single parsed log record."""
    timestamp: datetime
    service: str
    message: str
    raw: str


def parse_log_line(line: str) -> LogEntry:
    """Parse a log line of the form ``<timestamp> <service> <message>``.

    Example::

        2024-06-01T10:00:00-04:00 service-a Starting up

    Returns
    -------
    LogEntry
    """
    parts = line.strip().split(" ", 2)
    if len(parts) < 3:
        raise ValueError(f"Malformed log line: {line!r}")

    ts_raw, service, message = parts
    ts = parse_timestamp(ts_raw)
    return LogEntry(timestamp=ts, service=service, message=message, raw=line.strip())
