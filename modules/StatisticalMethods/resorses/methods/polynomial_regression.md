# Polynomial Regression Implementation

```python
from typing import Dict, Any, List

def calculate_polynomial_regression(X: List[List[float]], y: List[float], degree: int = 2) -> Dict[str, Any]:
    """
    Calculates Polynomial Regression of a given degree.
    """
    import numpy as np
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.linear_model import LinearRegression
    from sklearn.pipeline import make_pipeline

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = make_pipeline(PolynomialFeatures(degree), LinearRegression())
    model.fit(X_arr, y_arr)
    
    # Get the regression model from the pipeline
    reg_model = model.named_steps['linearregression']
    
    return {
        "degree": degree,
        "coefficients": reg_model.coef_.tolist(),
        "intercept": float(reg_model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }
```
