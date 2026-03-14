import pandas as pd
import numpy as np
import pytest
from src.merger import merge_user_activity


def test_all_users_preserved_when_some_have_no_activity():
    users = pd.DataFrame({"user_id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})
    activity = pd.DataFrame({"user_id": [1, 3], "actions": [10, 5]})

    result = merge_user_activity(users, activity)

    assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
    assert set(result["user_id"].tolist()) == {1, 2, 3}
    bob_row = result[result["user_id"] == 2].iloc[0]
    assert np.isnan(bob_row["actions"]), "Bob should have NaN actions"


def test_all_users_present_when_activity_is_empty():
    users = pd.DataFrame({"user_id": [1, 2], "name": ["Alice", "Bob"]})
    activity = pd.DataFrame({"user_id": pd.Series([], dtype="int64"), "actions": pd.Series([], dtype="int64")})

    result = merge_user_activity(users, activity)

    assert len(result) == 2, f"Expected 2 rows, got {len(result)}"


def test_full_match_returns_all_data():
    users = pd.DataFrame({"user_id": [1, 2], "name": ["Alice", "Bob"]})
    activity = pd.DataFrame({"user_id": [1, 2], "actions": [10, 20]})

    result = merge_user_activity(users, activity)

    assert len(result) == 2
    assert result[result["user_id"] == 1].iloc[0]["actions"] == 10
    assert result[result["user_id"] == 2].iloc[0]["actions"] == 20


def test_custom_key_column():
    users = pd.DataFrame({"uid": [1, 2, 3], "name": ["A", "B", "C"]})
    activity = pd.DataFrame({"uid": [2], "score": [99]})

    result = merge_user_activity(users, activity, key="uid")

    assert len(result) == 3
    assert set(result["uid"].tolist()) == {1, 2, 3}
