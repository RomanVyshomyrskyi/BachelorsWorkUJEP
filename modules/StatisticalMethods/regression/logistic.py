"""
Logistic Regression Module - Classification.

Provides logistic regression for binary and multiclass classification tasks.
Despite the name, this is NOT a regression method — it predicts class labels
by modeling the probability of class membership using the logistic (sigmoid) function.
"""
from typing import Dict, Any, List


def calculate_logistic_regression(X: List[List[float]], y: List[int], C: float = 1.0) -> Dict[str, Any]:
    """
    Calculate Logistic Regression for classification tasks.

    Description:
        Fits a logistic regression model that predicts the probability that a sample
        belongs to each class using the logistic (sigmoid) function for binary classification
        or the softmax function for multiclass classification. The model is regularized
        to prevent overfitting.

        Use this method when:
          - The target variable is categorical (class labels), not continuous.
          - You need predicted class probabilities, not just hard labels.
          - You want a fast, interpretable baseline classifier.
          - Features have a roughly linear relationship with the log-odds of the target.

        IMPORTANT: Unlike regression methods, this function returns:
          - 'score_accuracy': Classification accuracy (fraction of correct predictions),
            NOT R-squared.
          - 'classes': The unique class labels learned from the training data.

        The 'C' parameter controls inverse regularization strength:
          - C=1.0 is the default (moderate regularization).
          - Higher C = less regularization = model fits training data more closely
            (risk of overfitting).
          - Lower C = more regularization = simpler model (risk of underfitting).

    Args:
        X: Feature matrix as a list of lists. Shape: (n_samples, n_features).
        y: Class labels as a flat list of integers (e.g., [0, 1, 0, 1, 1]).
           Can also be string labels — they will be encoded internally.
        C: Inverse of regularization strength (positive float). Default is 1.0.
           Smaller values specify stronger regularization.

    Returns:
        A dict containing:
            - 'coefficients' (List[List[float]]): Weight matrix for each class
              (shape: n_classes x n_features). Each row gives the weights for one class.
            - 'intercept' (List[float]): Bias term for each class.
            - 'score_accuracy' (float): Classification accuracy on the training data
              (fraction of correctly classified samples).
            - 'classes' (List[int]): The unique class labels sorted in ascending order.
    """
    import numpy as np
    from sklearn.linear_model import LogisticRegression

    # Convert Python lists to NumPy arrays for efficient numerical computation
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Instantiate the logistic regression classifier with inverse regularization strength C
    model = LogisticRegression(C=C)

    # Fit the model — learns weights that maximize the log-likelihood (cross-entropy loss)
    model.fit(X_arr, y_arr)

    # Return coefficients, intercept, classification accuracy, and learned class labels
    return {
        "coefficients": model.coef_.tolist(),
        "intercept": model.intercept_.tolist(),
        "score_accuracy": float(model.score(X_arr, y_arr)),
        "classes": model.classes_.tolist()
    }
