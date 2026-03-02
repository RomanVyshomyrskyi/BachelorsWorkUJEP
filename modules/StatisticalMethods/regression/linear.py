from typing import Dict, Any, List, Union

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

def calculate_ridge_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
    """
    Calculates Ridge Regression (L2 regularization).
    """
    import numpy as np
    from sklearn.linear_model import Ridge
    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = Ridge(alpha=alpha)
    model.fit(X_arr, y_arr)
    
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }

def calculate_lasso_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
    """
    Calculates Lasso Regression (L1 regularization).
    """
    import numpy as np
    from sklearn.linear_model import Lasso
    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = Lasso(alpha=alpha)
    model.fit(X_arr, y_arr)
    
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }
