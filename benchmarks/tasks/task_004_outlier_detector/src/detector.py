import numpy as np


def detect_outliers(
    data: np.ndarray,
    factor: float = 1.5,
) -> np.ndarray:
    """Detect outliers using the IQR (interquartile range) method.

    A value is considered an outlier if it falls below
    ``Q1 - factor * IQR`` or above ``Q3 + factor * IQR``, where Q1 and
    Q3 are the 25th and 75th percentiles respectively.

    Parameters
    ----------
    data : np.ndarray
        1-D numeric array.
    factor : float
        Multiplier for the IQR to set whisker length (default 1.5).

    Returns
    -------
    np.ndarray
        Boolean mask where ``True`` marks outliers.
    """
    q1 = np.percentile(data, 25)
    q3 = np.percentile(data, 75)
    iqr = q3 - q1
    mean = np.mean(data)

    lower_bound = mean - factor * iqr  # BUG: should use q1, not mean
    upper_bound = mean + factor * iqr  # BUG: should use q3, not mean

    return (data < lower_bound) | (data > upper_bound)


def remove_outliers(data: np.ndarray, factor: float = 1.5) -> np.ndarray:
    """Return a copy of *data* with outliers removed.

    Parameters
    ----------
    data : np.ndarray
        1-D numeric array.
    factor : float
        IQR multiplier (passed to :func:`detect_outliers`).

    Returns
    -------
    np.ndarray
        Filtered array.
    """
    mask = detect_outliers(data, factor)
    return data[~mask]
