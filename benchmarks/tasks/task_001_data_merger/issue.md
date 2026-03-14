# Bug: merge_user_activity drops users who have no activity records

## Description

The `merge_user_activity()` function is supposed to combine user profile data with their activity logs, producing a complete report. Users who have **no activity** should still appear in the result with `NaN` values for activity columns.

However, currently users without any activity records are **silently dropped** from the output. This causes downstream dashboards to undercount total users.

## Steps to reproduce

```python
import pandas as pd
from src.merger import merge_user_activity

users = pd.DataFrame({"user_id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})
activity = pd.DataFrame({"user_id": [1, 3], "actions": [10, 5]})

result = merge_user_activity(users, activity)
print(result)
# Expected: 3 rows (Bob should appear with NaN actions)
# Actual: 2 rows (Bob is missing)
```

## Expected behavior

All users from the `users` DataFrame should be present in the output, even if they have no matching activity records.
