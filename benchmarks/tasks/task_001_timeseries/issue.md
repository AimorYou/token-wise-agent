# Bug: `rolling_mean` window is off by one

## Description

The `rolling_mean()` function computes a moving average over a 1-D array. The `window` parameter is supposed to define how many elements are included in each average. However, the current implementation includes **window + 1** elements in each computation, producing incorrect results.

For example, with `window=3` and data `[1, 2, 3, 4, 5]`, the value at index 3 should be `mean([2, 3, 4]) = 3.0`, but the function returns `mean([1, 2, 3, 4]) = 2.5`.

## Steps to reproduce

```python
import numpy as np
from src.timeseries import rolling_mean

data = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
result = rolling_mean(data, window=3)
print(result)
# Expected: [nan, nan, 2.0, 3.0, 4.0]
# Actual:   [nan, nan, 1.5, 2.0, 3.0]  (wrong — window is 4 instead of 3)
```

## Expected behavior

`rolling_mean(data, window=3)` should average exactly 3 elements at each position. The first `window - 1` elements should be `NaN`.
