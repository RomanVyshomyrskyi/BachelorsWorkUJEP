"""
Polynomial Regression Module.

Provides polynomial regression by extending linear regression with polynomial feature
transformation. This allows fitting curved relationships while still leveraging the
efficiency and interpretability of linear model fitting.
"""
from typing import Dict, Any, List


def calculate_polynomial_regression(X: List[List[float]], y: List[float], degree: int = 2) -> Dict[str, Any]:
    """
    Calculate Polynomial Regression of a given degree.
        Transforms the input features into polynomial features (e.g., x1, x1^2, x1*x2, ...)
        up to the specified degree, then fits a linear regression model on those transformed
        features. This enables modeling non-linear relationships as a linear combination of
        polynomial basis functions.

        Use this method when:
          - The relationship between features and target appears curved (quadratic, cubic, etc.).
          - You want to capture trends that simple linear regression cannot.
          - You need interpretability (coefficients map to polynomial terms).

        WARNING: Higher degrees can lead to overfitting (the model fits noise in the training
        data). Always validate on held-out data and start with degree=2 or 3.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        degree: Degree of the polynomial features to generate. Default is 2 (quadratic).
                degree=2 produces x, x^2 and all cross-terms; degree=3 adds cubes, etc.

    Returns:
        A dict containing:
            - 'degree' (int): The polynomial degree used.
            - 'coefficients' (List[float]): The learned coefficients for each polynomial term.
            - 'intercept' (float): The y-intercept (bias term) of the fitted linear model.
            - 'score_r2' (float): R-squared coefficient of determination on the training data.
    """
    import numpy as np
    # PolynomialFeatures generates the transformed feature matrix (x, x^2, ..., cross-terms)
    from sklearn.preprocessing import PolynomialFeatures
    from sklearn.linear_model import LinearRegression
    # make_pipeline chains the polynomial transformation and linear regression together
    from sklearn.pipeline import make_pipeline

    # Convert Python lists to NumPy arrays for efficient numerical computation
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Build a pipeline: first transform features to polynomial basis, then fit linear regression
    model = make_pipeline(PolynomialFeatures(degree), LinearRegression())

    # Fit the pipeline — internally applies polynomial transformation then fits OLS
    model.fit(X_arr, y_arr)

    # Extract the underlying LinearRegression object from the pipeline to access coefficients
    reg_model = model.named_steps['linearregression']

    # Return the polynomial degree, learned coefficients, intercept, and goodness-of-fit
    return {
        "degree": degree,
        "coefficients": reg_model.coef_.tolist(),
        "intercept": float(reg_model.intercept_),
        "score_r2": float(model.score(X_arr, y_arr))
    }
