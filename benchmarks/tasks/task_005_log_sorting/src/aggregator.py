"""Aggregate and sort log entries from multiple sources."""

from __future__ import annotations

from .log_parser import LogEntry, parse_log_line


def aggregate_logs(sources: list[list[str]]) -> list[LogEntry]:
    """Merge log lines from several sources and sort by timestamp.

    Parameters
    ----------
    sources : list[list[str]]
        Each inner list contains raw log lines from one service.

    Returns
    -------
    list[LogEntry]
        All entries merged and sorted by ascending timestamp.
    """
    entries: list[LogEntry] = []
    for source in sources:
        for line in source:
            entries.append(parse_log_line(line))

    entries.sort(key=lambda e: e.timestamp)
    return entries
