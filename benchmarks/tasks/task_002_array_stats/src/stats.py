import numpy as np


def compute_std(data: np.ndarray, axis: int | None = None) -> float | np.ndarray:
    """Compute the **sample** standard deviation of the data.

    Uses Bessel's correction (ddof=1) so that the result is an unbiased
    estimator of the population standard deviation when computed from a
    sample.

    Parameters
    ----------
    data : np.ndarray
        Input array.
    axis : int or None
        Axis along which to compute. ``None`` computes over the flattened
        array.

    Returns
    -------
    float or np.ndarray
        Sample standard deviation.
    """
    return np.std(data, axis=axis)


def compute_zscore(data: np.ndarray) -> np.ndarray:
    """Standardise *data* to z-scores using the sample mean and sample std.

    Parameters
    ----------
    data : np.ndarray
        1-D input array.

    Returns
    -------
    np.ndarray
        Array of z-scores.
    """
    mean = np.mean(data)
    std = compute_std(data)
    if std == 0:
        return np.zeros_like(data, dtype=float)
    return (data - mean) / std


def confidence_interval(data: np.ndarray, confidence: float = 0.95) -> tuple[float, float]:
    """Compute a symmetric confidence interval around the sample mean.

    Uses the normal approximation (z*) for the given confidence level.

    Parameters
    ----------
    data : np.ndarray
        1-D input array.
    confidence : float
        Confidence level (e.g. 0.95 for 95%).

    Returns
    -------
    tuple[float, float]
        (lower_bound, upper_bound)
    """
    z_map = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_map.get(confidence, 1.96)
    mean = np.mean(data)
    std = compute_std(data)
    n = len(data)
    margin = z * std / np.sqrt(n)
    return (mean - margin, mean + margin)
