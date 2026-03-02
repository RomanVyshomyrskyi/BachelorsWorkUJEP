from typing import Dict, Any, List

def calculate_support_vector_regression(X: List[List[float]], y: List[float], kernel: str = 'rbf', C: float = 1.0, epsilon: float = 0.1) -> Dict[str, Any]:
    """
    Calculates Support Vector Regression.
    """
    import numpy as np
    from sklearn.svm import SVR

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = SVR(kernel=kernel, C=C, epsilon=epsilon)
    model.fit(X_arr, y_arr)
    
    return {
        "kernel": kernel,
        "score_r2": float(model.score(X_arr, y_arr)),
        "params": {
            "C": C,
            "epsilon": epsilon
        }
    }
