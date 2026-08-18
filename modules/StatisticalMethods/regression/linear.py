"""
Linear Regression Module - Ordinary Least Squares, Ridge, and Lasso.

Provides three linear regression implementations:
  - Ordinary Least Squares (unregularized)
  - Ridge (L2-penalized) for handling multicollinearity
  - Lasso (L1-penalized) for automatic feature selection

All functions accept Python lists and return dicts with coefficients, intercept,
and an R-squared score.
"""
from typing import Dict, Any, List, Union


def calculate_linear_regression(X: List[List[float]], y: List[float]) -> Dict[str, Any]:
    """
    Calculate Ordinary Least Squares (OLS) linear regression.
        Fits a linear model by minimizing the residual sum of squares between the
        observed targets and those predicted by a linear approximation. Supports both
        simple regression (one feature) and multiple regression (many features).

        Use this method when you want a baseline, unregularized model with no penalty
        on coefficient size. It works well when features are independent and the
        relationship is approximately linear.

    Args:
        X: Feature matrix as a list of lists. Each inner list is one sample
           and each element within it is a feature value. Shape: (n_samples, n_features).
        y: Target values as a flat list. Length must equal the number of rows in X.

    Returns:
        A dict containing:
            - 'coefficients' (List[float]): The learned slope coefficients for each feature.
            - 'intercept' (float): The y-intercept (bias term) of the fitted model.
            - 'score_r2' (float): The R-squared coefficient of determination
                (1.0 = perfect fit, 0.0 = baseline, negative = worse than baseline).

        Examples:
            >>> result = calculate_linear_regression(
            ...     X=[[1.0], [2.0], [3.0], [4.0], [5.0]],
            ...     y=[2.0, 4.0, 6.0, 8.0, 10.0])
            >>> round(result["intercept"], 4)
            0.0
            >>> round(result["coefficients"][0], 4)
            2.0
            >>> round(result["score_r2"], 4)
            1.0
    """
    import numpy as np
    from sklearn.linear_model import LinearRegression

    # Convert Python lists to NumPy arrays for efficient numerical computation with scikit-learn
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the OLS linear regression model (no regularization)
    model = LinearRegression()

    # Fit the model by finding coefficients that minimize the residual sum of squares
    model.fit(X_arr, y_arr)

    # Return the learned parameters and the R-squared goodness-of-fit score
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }


def calculate_ridge_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
    """
    Calculate Ridge Regression with L2 regularization.
        Fits a linear model with L2 penalty on the size of coefficients. The regularization
        term (L2 norm squared) is added to the loss function, which shrinks coefficients
        toward zero but never eliminates them completely.

        Use this method when:
          - Features are highly correlated (multicollinearity).
          - You want to reduce model variance without dropping features entirely.
          - You have many features and want to prevent overfitting while keeping all of them.

        The 'alpha' parameter controls regularization strength:
          - alpha=0 reduces to ordinary least squares.
          - Higher alpha = stronger penalty = smaller coefficients = simpler model.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        alpha: Regularization strength (positive float). Default is 1.0.
               Higher values increase the penalty on large coefficients.

    Returns:
        A dict containing:
            - 'coefficients' (List[float]): The L2-shrunk slope coefficients.
            - 'intercept' (float): The y-intercept of the fitted model.
            - 'score_r2' (float): R-squared coefficient of determination.

        Examples:
            >>> result = calculate_ridge_regression(
            ...     X=[[1.0, 2.0], [2.0, 4.0], [3.0, 6.0], [4.0, 8.0]],
            ...     y=[1.0, 2.0, 3.0, 4.0],
            ...     alpha=0.5)
            >>> len(result["coefficients"])
            2
            >>> isinstance(result["intercept"], float)
            True
            >>> 0.0 <= result["score_r2"] <= 1.0
            True
    """
    import numpy as np
    from sklearn.linear_model import Ridge

    # Convert Python lists to NumPy arrays for efficient numerical computation with scikit-learn
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the Ridge model with L2 regularization strength 'alpha'
    model = Ridge(alpha=alpha)

    # Fit the model — minimizes RSS + alpha * (sum of squared coefficients)
    model.fit(X_arr, y_arr)

    # Return the learned parameters and the R-squared goodness-of-fit score
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }


def calculate_lasso_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
    """
    Calculate Lasso Regression with L1 regularization.
        Fits a linear model with L1 penalty on the size of coefficients. The regularization
        term (L1 norm) is added to the loss function, which can shrink some coefficients
        all the way to exactly zero — effectively performing automatic feature selection.

        Use this method when:
          - You have many features and suspect only a subset is relevant.
          - You want built-in feature selection (sparse model).
          - Interpretability is important and you need to identify key predictors.

        The 'alpha' parameter controls regularization strength:
          - alpha=0 reduces to ordinary least squares.
          - Higher alpha = stronger penalty = more coefficients driven to zero = fewer features.

        WARNING: Lasso may arbitrarily select one feature among a group of correlated ones
        rather than keeping all of them. For groups of correlated features, consider
        Elastic Net instead.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        alpha: Regularization strength (positive float). Default is 1.0.
               Higher values produce sparser models with more zero coefficients.

    Returns:
        A dict containing:
            - 'coefficients' (List[float]): The L1-shrunk coefficients (some may be exactly 0).
            - 'intercept' (float): The y-intercept of the fitted model.
            - 'score_r2' (float): R-squared coefficient of determination.

        Examples:
            >>> result = calculate_lasso_regression(
            ...     X=[[1.0, 0.0], [2.0, 0.1], [3.0, 0.0], [4.0, 0.1]],
            ...     y=[1.0, 2.0, 3.0, 4.0],
            ...     alpha=0.1)
            >>> len(result["coefficients"])
            2
            >>> isinstance(result["intercept"], float)
            True
            >>> # some coefficients may be exactly zero (feature selection)
            >>> any(c == 0.0 for c in result["coefficients"])
            True
    """
    import numpy as np
    from sklearn.linear_model import Lasso

    # Convert Python lists to NumPy arrays for efficient numerical computation with scikit-learn
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the Lasso model with L1 regularization strength 'alpha'
    model = Lasso(alpha=alpha)

    # Fit the model — minimizes RSS + alpha * (sum of absolute coefficients)
    model.fit(X_arr, y_arr)

    # Return the learned parameters and the R-squared goodness-of-fit score
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": float(model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }
