import pandas as pd
import numpy as np
import pytest
from src.cleaner import fill_missing, drop_low_variance, normalize_columns


class TestFillMissing:
    def test_fills_with_column_median(self):
        df = pd.DataFrame({
            "age": [25.0, np.nan, 35.0, 45.0],
            "salary": [50000.0, 60000.0, np.nan, 80000.0],
        })
        result = fill_missing(df)

        # median of age (non-NaN): median([25, 35, 45]) = 35
        assert result.loc[1, "age"] == 35.0, f"Expected 35.0, got {result.loc[1, 'age']}"
        # median of salary (non-NaN): median([50000, 60000, 80000]) = 60000
        assert result.loc[2, "salary"] == 60000.0, f"Expected 60000.0, got {result.loc[2, 'salary']}"

    def test_no_nans_in_output(self):
        df = pd.DataFrame({
            "a": [1.0, np.nan, 3.0],
            "b": [np.nan, 5.0, 6.0],
        })
        result = fill_missing(df)
        assert not result.isna().any().any(), "Result should have no NaN values"

    def test_no_nans_unchanged(self):
        df = pd.DataFrame({"x": [1.0, 2.0, 3.0], "y": [4.0, 5.0, 6.0]})
        result = fill_missing(df)
        pd.testing.assert_frame_equal(result, df)

    def test_does_not_modify_input(self):
        df = pd.DataFrame({"a": [1.0, np.nan, 3.0]})
        _ = fill_missing(df)
        assert df.loc[1, "a"] is np.nan or np.isnan(df.loc[1, "a"])

    def test_each_column_uses_own_median(self):
        df = pd.DataFrame({
            "small": [1.0, 2.0, np.nan],     # median = 1.5
            "large": [1000.0, 2000.0, np.nan],  # median = 1500.0
        })
        result = fill_missing(df)
        assert result.loc[2, "small"] == 1.5
        assert result.loc[2, "large"] == 1500.0


class TestDropLowVariance:
    def test_drops_constant_column(self):
        df = pd.DataFrame({"a": [1, 1, 1], "b": [1, 2, 3]})
        result = drop_low_variance(df)
        assert "a" not in result.columns
        assert "b" in result.columns


class TestNormalizeColumns:
    def test_output_range(self):
        df = pd.DataFrame({"x": [10.0, 20.0, 30.0]})
        result = normalize_columns(df)
        assert result["x"].min() == 0.0
        assert result["x"].max() == 1.0
