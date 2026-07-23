"""
Nonlinear Regression Module.

Provides nonlinear regression by fitting user-specified parametric models using
scipy's curve_fit (Levenberg-Marquardt or trust-region reflective algorithm).
This allows fitting arbitrary nonlinear relationships beyond polynomial forms.
"""
from typing import Dict, Any, List, Callable


def calculate_nonlinear_regression(X: List[float], y: List[float], model_func: Callable, p0: List[float] = None) -> Dict[str, Any]:
    """
    Calculate Nonlinear Regression for a user-specified parametric model function.

    Description:
        Fits a nonlinear model to the data by minimizing the sum of squared residuals
        using scipy.optimize.curve_fit. The user provides a callable model function that
        describes the expected relationship between inputs and outputs, and the algorithm
        finds the optimal parameter values.

        Use this method when:
          - The relationship between features and target follows a known nonlinear form
            (exponential decay, growth curves, saturation, sinusoidal, etc.).
          - You have a theoretical model and want to estimate its parameters from data.
          - Polynomial regression is insufficient to capture the relationship.

        The 'model_func' parameter must be a callable with the signature:
            model_func(x, *params) -> array_like
        where 'x' is the independent variable and 'params' are the parameters to estimate.

        Examples of valid model_func strings (passed as lambda via eval in the MCP wrapper):
          - Exponential growth:  'lambda x, a, b: a * np.exp(b * x)'
          - Exponential decay:   'lambda x, a, b: a * np.exp(-b * x)'
          - Power law:           'lambda x, a, b: a * x ** b'
          - Sinusoidal:          'lambda x, a, b, c: a * np.sin(b * x + c)'
          - Logistic growth:     'lambda x, a, b, c: a / (1 + np.exp(-b * (x - c)))'

        The 'p0' parameter (optional) provides initial guesses for the parameters.
        Good initial guesses are critical for convergence — poor guesses can cause
        the optimizer to fail or converge to a local minimum.

        The function returns the estimated parameters, their covariance matrix (for
        uncertainty estimation), and an R-squared goodness-of-fit score.

    Args:
        X: Feature values as a flat list (single-feature nonlinear regression only).
           Shape should be (n_samples,) or (n_samples, 1).
        y: Target values as a flat list. Length must equal the length of X.
        model_func: A callable Python function that defines the nonlinear model.
            Must accept the independent variable as the first argument followed by
            the parameters to estimate. Example:
                def my_model(x, a, b):
                    return a * np.exp(-b * x)
            The number of parameters (after x) determines the dimensionality of p0.
        p0: Initial guesses for the model parameters (optional list of floats).
            Length must match the number of parameters in model_func.
            If not provided, scipy will use 1.0 for each parameter.

    Returns:
        A dict containing:
            - 'parameters' (List[float]): The optimal parameter values (popt) that
              minimize the sum of squared residuals between the model and data.
            - 'covariance' (List[List[float]]): The estimated covariance of popt.
              The diagonal elements represent the variance of each parameter estimate
              — larger values indicate less certainty about that parameter.
            - 'score_r2' (float): R-squared coefficient of determination computed as
              1 - (SS_res / SS_tot), where SS_res is the residual sum of squares and
              SS_tot is the total sum of squares.
    """
    import numpy as np
    # curve_fit uses iterative optimization (Levenberg-Marquardt) to find parameters
    # that minimize the sum of squared differences between model predictions and actual y
    from scipy.optimize import curve_fit

    # Convert Python lists to NumPy arrays for numerical computation and scipy compatibility
    X_arr = np.array(X)
    y_arr = np.array(y)

    # Fit the nonlinear model using least-squares optimization
    # popt = optimal parameter values, pcov = covariance matrix of popt
    popt, pcov = curve_fit(model_func, X_arr, y_arr, p0=p0)

    # Calculate R-squared: first compute the residuals (actual - predicted values)
    residuals = y_arr - model_func(X_arr, *popt)

    # Sum of squared residuals (unexplained variance)
    ss_res = np.sum(residuals**2)

    # Total sum of squares (total variance around the mean)
    ss_tot = np.sum((y_arr - np.mean(y_arr))**2)

    # R-squared = 1 - (unexplained variance / total variance); 1.0 = perfect fit
    r2 = 1 - (ss_res / ss_tot)

    # Return the optimal parameters, their covariance, and the goodness-of-fit score
    return {
        "parameters": popt.tolist(),
        "covariance": pcov.tolist(),
        "score_r2": float(r2)
    }
