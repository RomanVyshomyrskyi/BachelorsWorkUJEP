"""
Decision Tree and Random Forest Regression Module.

Provides tree-based regression methods that partition the feature space into
regions and predict the mean target value within each region. These methods
handle nonlinear relationships and feature interactions automatically without
requiring feature scaling.
"""
from typing import Dict, Any, List


def calculate_decision_tree_regression(X: List[List[float]], y: List[float], max_depth: int = None) -> Dict[str, Any]:
    """
    Calculate Decision Tree Regression.

    Description:
        Builds a single decision tree that recursively partitions the feature space
        into regions (nodes) by finding the feature and threshold that best split the
        data to minimize variance (MSE). Predictions for new samples are the mean target
        value of the training samples in the same leaf node.

        Use this method when:
          - You want an interpretable, transparent model (you can visualize the tree).
          - The relationship between features and target is highly nonlinear.
          - You have mixed feature types or need automatic feature selection.
          - You want to understand feature importance rankings.

        WARNING: Single decision trees are prone to overfitting (high variance). A tree
        trained on the full data may memorize noise. For better generalization, use
        Random Forest Regression (ensemble of trees) instead.

        The 'max_depth' parameter controls tree complexity:
          - max_depth=None (default): Tree grows until all leaves are pure or contain
            only one sample (high risk of overfitting).
          - max_depth=3-5: Shallow trees that generalize better but may underfit.
          - Tuning max_depth is the primary way to control overfitting in a single tree.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        max_depth: Maximum depth of the tree (number of levels). Default is None
                   (unlimited growth). Set to 3-10 for practical models.

    Returns:
        A dict containing:
            - 'max_depth' (int or None): The max_depth parameter used.
            - 'score_r2' (float): R-squared coefficient of determination on training data.
            - 'feature_importances' (List[float]): Importance score for each feature
              (sum of MSE reduction attributed to that feature across all splits).
              Values range from 0.0 (unused) to 1.0 (most important). Sum equals 1.0.
    """
    import numpy as np
    from sklearn.tree import DecisionTreeRegressor

    # Convert Python lists to NumPy arrays for efficient numerical computation
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the decision tree regressor with optional depth constraint
    model = DecisionTreeRegressor(max_depth=max_depth)

    # Fit the tree — recursively splits data to minimize variance (MSE) at each node
    model.fit(X_arr, y_arr)

    # Return tree configuration, goodness-of-fit, and feature importance rankings
    return {
        "max_depth": max_depth,
        "score_r2": float(model.score(X_arr, y_arr)),
        "feature_importances": model.feature_importances_.tolist()
    }


def calculate_random_forest_regression(X: List[List[float]], y: List[float], n_estimators: int = 100, max_depth: int = None) -> Dict[str, Any]:
    """
    Calculate Random Forest Regression.

    Description:
        Builds an ensemble of decision trees (a "forest") where each tree is trained on
        a bootstrap sample (random sample with replacement) of the training data and
        considers a random subset of features at each split. The final prediction is the
        average of all tree predictions, which reduces variance compared to a single tree.

        Use this method when:
          - You need better predictive accuracy than a single decision tree.
          - You want robust predictions that generalize well to new data.
          - You have many features and don't want to manually select them.
          - You need reliable feature importance rankings.

        Random Forests are considered one of the best off-the-shelf regression methods
        because they:
          - Handle nonlinear relationships and feature interactions automatically.
          - Are robust to outliers and noise in the data.
          - Do not require feature scaling or normalization.
          - Provide built-in feature importance estimates.

        The 'n_estimators' parameter controls the number of trees in the forest:
          - n_estimators=100 (default): Good starting point for most problems.
          - More trees = better performance but slower training (diminishing returns after ~300).
          - Random Forest predictions are stable once n_estimators is sufficiently large.

        The 'max_depth' parameter controls each tree's complexity:
          - max_depth=None: Each tree grows fully (may overfit individual trees, but ensemble
            averaging mitigates this).
          - max_depth=5-20: Constrain tree depth for faster training and less overfitting.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        n_estimators: Number of decision trees in the forest. Default is 100.
                      Higher values improve accuracy up to a point (usually 200-500).
        max_depth: Maximum depth of each tree. Default is None (unlimited growth).
                   Setting this limits tree complexity and training time.

    Returns:
        A dict containing:
            - 'n_estimators' (int): Number of trees in the forest.
            - 'max_depth' (int or None): The max_depth parameter used.
            - 'score_r2' (float): R-squared coefficient of determination on training data.
            - 'feature_importances' (List[float]): Average importance score for each feature
              across all trees (based on mean decrease in MSE when the feature is used for splits).
              Values range from 0.0 to 1.0 and sum to 1.0.
    """
    import numpy as np
    from sklearn.ensemble import RandomForestRegressor

    # Convert Python lists to NumPy arrays for efficient numerical computation
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the random forest regressor with ensemble size and depth constraints
    model = RandomForestRegressor(n_estimators=n_estimators, max_depth=max_depth)

    # Fit the forest — trains n_estimators trees on bootstrap samples with random feature subsets
    model.fit(X_arr, y_arr)

    # Return ensemble configuration, goodness-of-fit, and averaged feature importance rankings
    return {
        "n_estimators": n_estimators,
        "max_depth": max_depth,
        "score_r2": float(model.score(X_arr, y_arr)),
        "feature_importances": model.feature_importances_.tolist()
    }
