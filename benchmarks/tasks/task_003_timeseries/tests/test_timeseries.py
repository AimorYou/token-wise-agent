import numpy as np
import pytest
from src.timeseries import rolling_mean, exponential_moving_average


class TestRollingMean:
    def test_basic_window_3(self):
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean(data, window=3)

        assert np.isnan(result[0])
        assert np.isnan(result[1])
        np.testing.assert_allclose(result[2], 2.0)  # mean([1,2,3])
        np.testing.assert_allclose(result[3], 3.0)  # mean([2,3,4])
        np.testing.assert_allclose(result[4], 4.0)  # mean([3,4,5])

    def test_window_1_returns_original(self):
        data = np.array([10.0, 20.0, 30.0])
        result = rolling_mean(data, window=1)
        np.testing.assert_allclose(result, data)

    def test_window_equals_length(self):
        data = np.array([2.0, 4.0, 6.0])
        result = rolling_mean(data, window=3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])
        np.testing.assert_allclose(result[2], 4.0)  # mean([2,4,6])

    def test_nan_count(self):
        data = np.arange(10.0)
        result = rolling_mean(data, window=5)
        nan_count = np.isnan(result).sum()
        assert nan_count == 4, f"Expected 4 NaNs, got {nan_count}"

    def test_window_2(self):
        data = np.array([1.0, 3.0, 5.0, 7.0])
        result = rolling_mean(data, window=2)
        assert np.isnan(result[0])
        np.testing.assert_allclose(result[1], 2.0)  # mean([1,3])
        np.testing.assert_allclose(result[2], 4.0)  # mean([3,5])
        np.testing.assert_allclose(result[3], 6.0)  # mean([5,7])

    def test_invalid_window(self):
        with pytest.raises(ValueError):
            rolling_mean(np.array([1.0]), window=0)


class TestExponentialMovingAverage:
    def test_alpha_1_returns_original(self):
        data = np.array([1.0, 2.0, 3.0])
        result = exponential_moving_average(data, alpha=1.0)
        np.testing.assert_allclose(result, data)

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            exponential_moving_average(np.array([1.0]), alpha=0.0)
