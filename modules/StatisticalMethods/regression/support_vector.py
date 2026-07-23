"""
Support Vector Regression Module.

Provides Support Vector Regression (SVR) which extends Support Vector Machines to
regression tasks. SVR finds a function that deviates from the actual targets by no
more than a specified threshold (epsilon), while minimizing model complexity.
"""
from typing import Dict, Any, List


def calculate_support_vector_regression(X: List[List[float]], y: List[float], kernel: str = 'rbf', C: float = 1.0, epsilon: float = 0.1) -> Dict[str, Any]:
    """
    Calculate Support Vector Regression (SVR).

    Description:
        Fits an SVR model that finds a hyperplane in a high-dimensional space such that
        all training data points are within a margin of width epsilon (the insensitive
        loss tube). Support vectors — the data points closest to the margin — determine
        the final model.

        Use this method when:
          - The relationship between features and target is complex and nonlinear.
          - You have a relatively small to medium-sized dataset (SVR doesn't scale well
            to very large datasets — O(n^2) to O(n^3) training complexity).
          - You need robust predictions in high-dimensional feature spaces.
          - You want to control the trade-off between model complexity and fitting error
            via the C and epsilon parameters.

        The kernel parameter defines the decision boundary:
          - 'linear': Linear boundary — equivalent to linear regression with regularization.
          - 'rbf' (default): Radial basis function — maps to infinite-dimensional space,
            capable of fitting highly nonlinear relationships. Most commonly used.
          - 'poly': Polynomial kernel — adds polynomial feature interaction terms.
          - 'sigmoid': Sigmoid kernel — similar to a two-layer neural network.

        The C parameter controls regularization (trade-off between flatness and errors):
          - C=1.0 (default): Moderate regularization.
          - Higher C = less regularization = smaller margin tolerance = more support vectors
            (risk of overfitting).
          - Lower C = more regularization = wider margin = fewer support vectors
            (risk of underfitting).

        The epsilon parameter defines the width of the insensitive loss tube:
          - epsilon=0.1 (default): Errors within +/-0.1 are ignored (no penalty).
          - Larger epsilon = more points fall within the tube = simpler model (more sparsity).
          - epsilon=0 reduces to standard regression with L1 loss on residuals.

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Target values as a flat list.
        kernel: Kernel function type used in the algorithm. Options: 'linear', 'rbf',
                'poly', 'sigmoid'. Default is 'rbf' (radial basis function).
        C: Regularization parameter (positive float). Default is 1.0.
           Higher values increase penalty for errors outside the epsilon tube.
        epsilon: Width of the epsilon-insensitive zone (non-negative float).
                 Default is 0.1. Errors within this tube are not penalized.

    Returns:
        A dict containing:
            - 'kernel' (str): The kernel function used.
            - 'score_r2' (float): R-squared coefficient of determination on training data.
              NOTE: SVR does not natively output coefficients because the model is defined
              in kernel space. The R-squared is the only direct performance metric provided.
            - 'params' (Dict): The hyperparameters used for the model, including:
              - 'C' (float): Regularization parameter.
              - 'epsilon' (float): Insensitive loss tube width.
    """
    import numpy as np
    from sklearn.svm import SVR

    # Convert Python lists to NumPy arrays for efficient numerical computation
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the SVR model with kernel, regularization, and loss tube parameters
    model = SVR(kernel=kernel, C=C, epsilon=epsilon)

    # Fit the SVR model — finds support vectors and optimal hyperplane within the epsilon tube
    model.fit(X_arr, y_arr)

    # Return kernel type, goodness-of-fit score, and the hyperparameters used
    return {
        "kernel": kernel,
        "score_r2": float(model.score(X_arr, y_arr)),
        "params": {
            "C": C,
            "epsilon": epsilon
        }
    }
