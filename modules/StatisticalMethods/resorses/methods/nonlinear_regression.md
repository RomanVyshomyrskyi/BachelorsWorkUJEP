# Nonlinear Regression Implementation

```python
from typing import Dict, Any, List, Callable

def calculate_nonlinear_regression(X: List[float], y: List[float], model_func: Callable, p0: List[float] = None) -> Dict[str, Any]:
    """
    Calculates Nonlinear Regression for a given model function.
    """
    import numpy as np
    from scipy.optimize import curve_fit

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    popt, pcov = curve_fit(model_func, X_arr, y_arr, p0=p0)
    
    # Calculate R-squared
    residuals = y_arr - model_func(X_arr, *popt)
    ss_res = np.sum(residuals**2)
    ss_tot = np.sum((y_arr - np.mean(y_arr))**2)
    r2 = 1 - (ss_res / ss_tot)
    
    return {
        "parameters": popt.tolist(),
        "covariance": pcov.tolist(),
        "score_r2": float(r2)
    }
```
