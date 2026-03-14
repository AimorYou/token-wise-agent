# Bug: `detect_outliers` computes IQR bounds relative to mean instead of quartiles

## Description

The `detect_outliers()` function uses the IQR method to flag outliers. The standard IQR rule defines outliers as values below `Q1 - 1.5 * IQR` or above `Q3 + 1.5 * IQR`.

However, the current implementation computes the whisker bounds relative to the **mean** instead of Q1/Q3, which produces incorrect outlier masks — especially for skewed distributions.

## Steps to reproduce

```python
import numpy as np
from src.detector import detect_outliers

data = np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 100])
mask = detect_outliers(data)
print(mask)
# Expected: only index 9 (value 100) is True
# Actual: incorrect mask because bounds are computed from the mean
```

## Expected behavior

The lower bound should be `Q1 - 1.5 * IQR` and the upper bound should be `Q3 + 1.5 * IQR`, where `Q1` is the 25th percentile and `Q3` is the 75th percentile.
