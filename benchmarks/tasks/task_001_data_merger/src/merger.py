import pandas as pd


def merge_user_activity(
    users: pd.DataFrame,
    activity: pd.DataFrame,
    key: str = "user_id",
) -> pd.DataFrame:
    """Merge user profiles with activity logs.

    Every user from the `users` DataFrame must appear in the result,
    even if they have no corresponding activity records (activity columns
    should be filled with NaN in that case).

    Parameters
    ----------
    users : pd.DataFrame
        User profile data. Must contain the `key` column.
    activity : pd.DataFrame
        Activity log data. Must contain the `key` column.
    key : str
        Column name to join on.

    Returns
    -------
    pd.DataFrame
        Merged DataFrame with all users preserved.
    """
    merged = pd.merge(users, activity, on=key, how="inner")
    return merged
