from typing import Dict, Any, List

def calculate_decision_tree_regression(X: List[List[float]], y: List[float], max_depth: int = None) -> Dict[str, Any]:
    """
    Calculates Decision Tree Regression.
    """
    import numpy as np
    from sklearn.tree import DecisionTreeRegressor

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = DecisionTreeRegressor(max_depth=max_depth)
    model.fit(X_arr, y_arr)
    
    return {
        "max_depth": max_depth,
        "score_r2": float(model.score(X_arr, y_arr)),
        "feature_importances": model.feature_importances_.tolist()
    }

def calculate_random_forest_regression(X: List[List[float]], y: List[float], n_estimators: int = 100, max_depth: int = None) -> Dict[str, Any]:
    """
    Calculates Random Forest Regression.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor

    X_arr = np.array(X)
    y_arr = np.array(y)
    
    model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth)
    model.fit(X_arr, y_arr)
    
    return {
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "score_r2": float(model.score(X_arr, y_arr)),
        "feature_importances": model.feature_importances_.tolist()
    }
