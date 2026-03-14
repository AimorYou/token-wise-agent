import numpy as np


def rolling_mean(data: np.ndarray, window: int) -> np.ndarray:
    """Compute the rolling (moving) mean over a 1-D array.

    For each position *i* the rolling mean is the average of the
    ``window`` elements ending at (and including) position *i*.
    Positions where a full window is not available are filled with
    ``np.nan``.

    Parameters
    ----------
    data : np.ndarray
        1-D numeric array.
    window : int
        Number of elements in the rolling window (must be >= 1).

    Returns
    -------
    np.ndarray
        Array of the same length as *data* with the rolling means.
    """
    if window < 1:
        raise ValueError("window must be >= 1")

    n = len(data)
    result = np.full(n, np.nan)

    for i in range(window - 1, n):
        start = i - window  # BUG: should be i - window + 1
        result[i] = np.mean(data[start:i + 1])

    return result


def exponential_moving_average(data: np.ndarray, alpha: float) -> np.ndarray:
    """Compute the exponential moving average (EMA).

    Parameters
    ----------
    data : np.ndarray
        1-D numeric array.
    alpha : float
        Smoothing factor in (0, 1].

    Returns
    -------
    np.ndarray
        EMA values.
    """
    if not (0 < alpha <= 1):
        raise ValueError("alpha must be in (0, 1]")

    result = np.empty(len(data))
    result[0] = data[0]
    for i in range(1, len(data)):
        result[i] = alpha * data[i] + (1 - alpha) * result[i - 1]
    return result
