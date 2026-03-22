"""Existing tests for log parsing and aggregation.

These tests cover log parsing and same-timezone sorting
that work correctly despite the timezone-awareness bug.
"""
from datetime import datetime

import pytest

from src.log_parser import parse_log_line
from src.aggregator import aggregate_logs


class TestParseLogLine:
    def test_basic(self):
        entry = parse_log_line("2024-06-01T12:00:00Z svc-a Hello world")
        assert entry.service == "svc-a"
        assert entry.message == "Hello world"

    def test_malformed_raises(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_log_line("incomplete")

    def test_multiword_message(self):
        entry = parse_log_line("2024-06-01T12:00:00Z svc-x This is a long message")
        assert entry.message == "This is a long message"


class TestAggregateLogs:
    def test_same_timezone_sorted_correctly(self):
        """Logs within the same timezone sort correctly by wall-clock time."""
        logs = [
            "2024-01-01T03:00:00Z svc-x Third",
            "2024-01-01T01:00:00Z svc-x First",
            "2024-01-01T02:00:00Z svc-x Second",
        ]
        merged = aggregate_logs([logs])
        messages = [e.message for e in merged]
        assert messages == ["First", "Second", "Third"]

    def test_empty_sources(self):
        assert aggregate_logs([]) == []
        assert aggregate_logs([[], []]) == []

    def test_single_entry(self):
        logs = ["2024-06-01T12:00:00Z svc-a Only entry"]
        merged = aggregate_logs([logs])
        assert len(merged) == 1
        assert merged[0].service == "svc-a"
