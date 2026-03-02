# Logistic Regression Implementation

```python
from typing import Dict, Any, List

def calculate_logistic_regression(X: List[List[float]], y: List[int], C: float = 1.0) -> Dict[str, Any]:
    """
    Calculates Logistic Regression for classification tasks.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = LogisticRegression(C=C)
    model.fit(X_arr, y_arr)
    
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
        "score_accuracy": float(model.score(X_arr, y_arr)),
        "classes": model.classes_.tolist()
    }
```
