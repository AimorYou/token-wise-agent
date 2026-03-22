"""Existing tests for timeseries module.

These tests cover EMA and rolling_mean edge cases that work correctly
despite the off-by-one bug.
"""
import numpy as np
import pytest
from src.timeseries import rolling_mean, exponential_moving_average


class TestRollingMean:
    def test_invalid_window_raises(self):
        """Window <= 0 must raise ValueError."""
        with pytest.raises(ValueError):
            rolling_mean(np.array([1.0]), window=0)

    def test_output_length_matches_input(self):
        """Output array must have the same length as input."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean(data, window=3)
        assert len(result) == len(data)

    def test_first_elements_are_nan(self):
        """First (window-1) elements should be NaN."""
        data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        result = rolling_mean(data, window=3)
        assert np.isnan(result[0])
        assert np.isnan(result[1])


class TestExponentialMovingAverage:
    def test_alpha_1_returns_original(self):
        """With alpha=1, EMA should just return original data."""
        data = np.array([1.0, 2.0, 3.0])
        result = exponential_moving_average(data, alpha=1.0)
        np.testing.assert_allclose(result, data)

    def test_invalid_alpha(self):
        with pytest.raises(ValueError):
            exponential_moving_average(np.array([1.0]), alpha=0.0)

    def test_ema_output_length(self):
        data = np.array([1.0, 2.0, 3.0, 4.0])
        result = exponential_moving_average(data, alpha=0.5)
        assert len(result) == len(data)

    def test_ema_first_value_equals_input(self):
        """First EMA value always equals the first input value."""
        data = np.array([10.0, 20.0, 30.0])
        result = exponential_moving_average(data, alpha=0.3)
        assert result[0] == data[0]
