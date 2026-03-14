# Bug: `fill_missing` fills NaN with median computed along wrong axis

## Description

The `fill_missing()` function should replace `NaN` values in each **column** with that column's median. This is the standard approach for imputing missing numerical data.

However, the current implementation computes the median along `axis=1` (rows) instead of `axis=0` (columns), causing values to be filled with the row median. This produces nonsensical results when columns represent different features with different scales.

## Steps to reproduce

```python
import pandas as pd
import numpy as np
from src.cleaner import fill_missing

df = pd.DataFrame({
    "age": [25, np.nan, 35, 45],
    "salary": [50000, 60000, np.nan, 80000],
})

result = fill_missing(df)
print(result)
# Expected: age NaN filled with median of [25, 35, 45] = 35
#           salary NaN filled with median of [50000, 60000, 80000] = 60000
# Actual:   wrong values because median is computed across rows
```

## Expected behavior

Each column's missing values should be filled with that column's own median.
