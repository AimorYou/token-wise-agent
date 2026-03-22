# Bug: Log entries are sorted incorrectly when timestamps differ in timezone

## Description

The log aggregation utility merges logs from multiple services.  However,
when logs contain timestamps from **different timezones**, the final ordering
is incorrect because the sorting compares naive string representations instead
of absolute UTC times.

## Steps to reproduce

```python
from src.aggregator import aggregate_logs

logs_us = [
    "2024-06-01T10:00:00-04:00 service-a Starting up",
    "2024-06-01T11:00:00-04:00 service-a Ready",
]
logs_eu = [
    "2024-06-01T14:30:00+02:00 service-b Starting up",  # = 12:30 UTC
]

merged = aggregate_logs([logs_us, logs_eu])
# Expected order by UTC:
#   10:00 EDT (14:00 UTC) → service-a Starting
#   14:30 CEST (12:30 UTC) → service-b Starting  ← should be FIRST
#   11:00 EDT (15:00 UTC) → service-a Ready
# Actual: sorted by string representation, so order is wrong.
```

## Expected behavior

Logs should be sorted by **absolute (UTC) time** regardless of the original
timezone in the timestamp.

## Notes

- `log_parser.py` parses individual log lines into structured records.
- `time_utils.py` has a `parse_timestamp()` helper — look at whether it
  preserves timezone information.
- `aggregator.py` merges and sorts the parsed records.

## Tests currently failing in

`tests/test_log_sorting.py`
