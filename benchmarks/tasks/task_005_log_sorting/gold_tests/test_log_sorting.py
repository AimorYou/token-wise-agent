from datetime import datetime, timezone, timedelta

import pytest

from src.log_parser import parse_log_line
from src.time_utils import parse_timestamp
from src.aggregator import aggregate_logs


# ------------------------------------------------------------------ time_utils
class TestParseTimestamp:
    def test_utc_z(self):
        ts = parse_timestamp("2024-06-01T12:00:00Z")
        assert ts == datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_positive_offset(self):
        ts = parse_timestamp("2024-06-01T14:30:00+02:00")
        expected = datetime(2024, 6, 1, 14, 30, 0,
                            tzinfo=timezone(timedelta(hours=2)))
        assert ts == expected

    def test_negative_offset(self):
        ts = parse_timestamp("2024-06-01T10:00:00-04:00")
        expected = datetime(2024, 6, 1, 10, 0, 0,
                            tzinfo=timezone(timedelta(hours=-4)))
        assert ts == expected

    def test_timestamps_comparable_across_zones(self):
        """14:30+02:00 (12:30 UTC) should be earlier than 10:00-04:00 (14:00 UTC)."""
        ts_eu = parse_timestamp("2024-06-01T14:30:00+02:00")
        ts_us = parse_timestamp("2024-06-01T10:00:00-04:00")
        assert ts_eu < ts_us


# ------------------------------------------------------------------ log_parser
class TestParseLogLine:
    def test_basic(self):
        entry = parse_log_line("2024-06-01T12:00:00Z svc-a Hello world")
        assert entry.service == "svc-a"
        assert entry.message == "Hello world"

    def test_malformed_raises(self):
        with pytest.raises(ValueError, match="Malformed"):
            parse_log_line("incomplete")


# ------------------------------------------------------------------ aggregator
class TestAggregateLogs:
    def test_merge_and_sort_across_timezones(self):
        logs_us = [
            "2024-06-01T10:00:00-04:00 svc-a Starting",   # 14:00 UTC
            "2024-06-01T11:00:00-04:00 svc-a Ready",      # 15:00 UTC
        ]
        logs_eu = [
            "2024-06-01T14:30:00+02:00 svc-b Starting",   # 12:30 UTC
        ]

        merged = aggregate_logs([logs_us, logs_eu])
        services = [e.service for e in merged]

        # Correct UTC order: svc-b (12:30), svc-a (14:00), svc-a (15:00)
        assert services == ["svc-b", "svc-a", "svc-a"]

    def test_same_timezone_sorted_correctly(self):
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

    def test_mixed_utc_and_offset(self):
        logs = [
            "2024-03-15T12:00:00Z svc-a Noon UTC",           # 12:00 UTC
            "2024-03-15T08:00:00-05:00 svc-b Morning EST",   # 13:00 UTC
            "2024-03-15T11:00:00-02:00 svc-c Late BRT",      # 13:00 UTC
        ]
        merged = aggregate_logs([logs])
        # svc-a at 12:00 UTC comes first
        assert merged[0].service == "svc-a"
