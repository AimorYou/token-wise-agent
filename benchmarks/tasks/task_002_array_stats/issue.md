# Bug: `compute_std` returns population std instead of sample std

## Description

The `compute_std()` function in `stats.py` is documented to return the **sample** standard deviation (ddof=1), which is the standard for statistical analysis of samples. However, it currently returns the **population** standard deviation (ddof=0).

This causes all downstream confidence interval calculations to be too narrow, leading to overconfident predictions.

## Steps to reproduce

```python
import numpy as np
from src.stats import compute_std

data = np.array([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0])
result = compute_std(data)
print(result)
# Expected: 2.0 (sample std, ddof=1)
# Actual:   ~1.87 (population std, ddof=0)
```

## Expected behavior

`compute_std` should use `ddof=1` (Bessel's correction) to compute the sample standard deviation, as documented in the docstring.
