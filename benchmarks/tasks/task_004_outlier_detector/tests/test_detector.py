import numpy as np
import pytest
from src.detector import detect_outliers, remove_outliers


class TestDetectOutliers:
    def test_obvious_outlier(self):
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], dtype=float)
        mask = detect_outliers(data)
        # 100 should be the only outlier
        assert mask[-1] == True, "100 should be detected as outlier"
        assert mask[:-1].sum() == 0, "No other values should be outliers"

    def test_no_outliers_in_uniform_data(self):
        data = np.array([4, 5, 5, 6, 6, 6, 7, 7, 8], dtype=float)
        mask = detect_outliers(data)
        assert mask.sum() == 0, "Uniform-ish data should have no outliers"

    def test_symmetric_outliers(self):
        data = np.array([-100, 1, 2, 3, 4, 5, 6, 7, 8, 9, 100], dtype=float)
        mask = detect_outliers(data)
        assert mask[0] == True, "-100 should be outlier"
        assert mask[-1] == True, "100 should be outlier"
        assert mask[1:-1].sum() == 0

    def test_custom_factor(self):
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20], dtype=float)
        # With a very large factor, nothing should be an outlier
        mask = detect_outliers(data, factor=100)
        assert mask.sum() == 0

    def test_bounds_use_quartiles_not_mean(self):
        # Skewed data where mean != midpoint of Q1 and Q3
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 50], dtype=float)
        q1 = np.percentile(data, 25)
        q3 = np.percentile(data, 75)
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr

        mask = detect_outliers(data)
        expected_mask = (data < lower) | (data > upper)
        np.testing.assert_array_equal(mask, expected_mask)


class TestRemoveOutliers:
    def test_removes_outlier(self):
        data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100], dtype=float)
        clean = remove_outliers(data)
        assert 100 not in clean
        assert len(clean) == 9
