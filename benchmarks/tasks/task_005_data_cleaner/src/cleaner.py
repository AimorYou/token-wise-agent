import pandas as pd
import numpy as np


def fill_missing(df: pd.DataFrame) -> pd.DataFrame:
    """Fill missing (NaN) values with the **column** median.

    Each column's NaN entries are replaced by the median of the
    non-NaN values in that same column. Columns with all NaN remain
    unchanged.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe (numeric columns only).

    Returns
    -------
    pd.DataFrame
        A new dataframe with NaN values filled.
    """
    result = df.copy()
    medians = result.median(axis=1)  # BUG: should be axis=0

    for col in result.columns:
        mask = result[col].isna()
        if mask.any():
            col_median = medians.get(col, np.nan) if isinstance(medians, pd.Series) else np.nan
            result.loc[mask, col] = col_median

    return result


def drop_low_variance(df: pd.DataFrame, threshold: float = 0.0) -> pd.DataFrame:
    """Drop columns whose variance is at or below *threshold*.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe.
    threshold : float
        Variance threshold.

    Returns
    -------
    pd.DataFrame
        DataFrame with low-variance columns removed.
    """
    variances = df.var()
    keep = variances[variances > threshold].index
    return df[keep]


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Min-max normalise each column to [0, 1].

    Columns where max == min are left as 0.

    Parameters
    ----------
    df : pd.DataFrame
        Input dataframe (numeric).

    Returns
    -------
    pd.DataFrame
        Normalised dataframe.
    """
    result = df.copy()
    for col in result.columns:
        col_min = result[col].min()
        col_max = result[col].max()
        if col_max - col_min == 0:
            result[col] = 0.0
        else:
            result[col] = (result[col] - col_min) / (col_max - col_min)
    return result
