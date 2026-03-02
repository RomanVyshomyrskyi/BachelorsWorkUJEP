# Linear Regression Implementation

```python
from typing import Dict, Any, List

def calculate_linear_regression(X: List[List[float]], y: List[float]) -> Dict[str, Any]:
    """
    Calculates Simple and Multiple Linear Regression.
    """
    import numpy as np
    from sklearn.linear_model import LinearRegression
    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = LinearRegression()
    model.fit(X_arr, y_arr)
    
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }

# Example use:
# X = [[1], [2], [3], [4], [5]]
# y = [2, 4, 6, 8, 10]
# result = calculate_linear_regression(X, y)
```
