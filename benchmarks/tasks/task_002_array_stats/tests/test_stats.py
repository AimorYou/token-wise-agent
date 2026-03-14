import numpy as np
import pytest
from src.stats import compute_std, compute_zscore, confidence_interval


class TestComputeStd:
    def test_sample_std_known_value(self):
        data = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        result = compute_std(data)
        expected = 2.0  # sample std with ddof=1
        assert abs(result - expected) < 1e-10, f"Expected {expected}, got {result}"

    def test_sample_std_simple(self):
        data = np.array([1.0, 3.0])
        result = compute_std(data)
        # sample std of [1, 3] with ddof=1 = sqrt(((1-2)^2 + (3-2)^2) / 1) = sqrt(2)
        expected = np.sqrt(2.0)
        assert abs(result - expected) < 1e-10

    def test_std_along_axis(self):
        data = np.array([[1.0, 3.0], [2.0, 4.0]])
        result = compute_std(data, axis=0)
        # sample std along axis 0: each column has 2 values
        # col 0: [1,2] -> std ddof=1 = sqrt(0.5) ≈ 0.7071
        expected = np.array([np.sqrt(0.5), np.sqrt(0.5)])
        np.testing.assert_allclose(result, expected)

    def test_single_element_returns_nan_or_zero(self):
        # With ddof=1, std of single element is technically undefined (0/0)
        # numpy returns nan, which is acceptable
        data = np.array([5.0])
        result = compute_std(data)
        # ddof=1 on single element -> division by 0 -> should not return 0.0
        assert np.isnan(result) or result != 0.0


class TestComputeZscore:
    def test_zscore_known_values(self):
        data = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        result = compute_zscore(data)
        mean = 5.0
        std = 2.0  # sample std
        expected = (data - mean) / std
        np.testing.assert_allclose(result, expected)

    def test_zscore_constant_array(self):
        data = np.array([3.0, 3.0, 3.0])
        result = compute_zscore(data)
        np.testing.assert_allclose(result, np.zeros(3))


class TestConfidenceInterval:
    def test_ci_95_known(self):
        data = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
        lo, hi = confidence_interval(data, 0.95)
        mean = 5.0
        std = 2.0  # sample std
        n = 8
        margin = 1.96 * std / np.sqrt(n)
        assert abs(lo - (mean - margin)) < 1e-10
        assert abs(hi - (mean + margin)) < 1e-10
