"""
StatisticalMethods Module - Machine Learning Regression Tools via Apache Superset MCP.

Provides a collection of statistical regression methods (linear, ridge, lasso, polynomial,
nonlinear, support vector, decision tree, random forest, and logistic regression) exposed
as MCP tools for data analysis and dashboard metric computation.

Usage:
    Register the module with a FastMCP instance and optionally a ModuleRegistry:

        from fastmcp import FastMCP
        from modules.StatisticalMethods import register
        mcp = FastMCP("my-server")
        register(mcp, registry)
"""
import os
import sys
import logging
from typing import Optional, List, Union, Dict, Any, Callable
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

from .regression.linear import calculate_linear_regression, calculate_ridge_regression, calculate_lasso_regression
from .regression.polynomial import calculate_polynomial_regression
from .regression.nonlinear import calculate_nonlinear_regression
from .regression.support_vector import calculate_support_vector_regression
from .regression.tree_forest import calculate_decision_tree_regression, calculate_random_forest_regression
from .regression.logistic import calculate_logistic_regression

depends_on = []


def get_module_api() -> Dict[str, Callable]:
    """
    Return the mapping of tool names to their underlying calculation functions.

    This dictionary is used by the ModuleRegistry to expose each regression method
    as a reusable callable across the application.

    Returns:
        A dict mapping tool name strings to the corresponding calculation function.
    """
    return {
        "linear_regression": calculate_linear_regression,
        "ridge_regression": calculate_ridge_regression,
        "lasso_regression": calculate_lasso_regression,
        "polynomial_regression": calculate_polynomial_regression,
        "nonlinear_regression": calculate_nonlinear_regression,
        "support_vector_regression": calculate_support_vector_regression,
        "decision_tree_regression": calculate_decision_tree_regression,
        "random_forest_regression": calculate_random_forest_regression,
        "logistic_regression": calculate_logistic_regression,
    }


def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    """
    Register all regression tools with the given FastMCP instance.

    Each registered tool accepts list-of-lists input for the feature matrix X and a
    list for the target vector y, returning a dict with the regression results.

    Args:
        mcp: The FastMCP server instance to register tools on.
        registry: Optional ModuleRegistry to also store the API mappings.
    """

    @mcp.tool(name="linear_regression", description="Calculates Simple and Multiple Linear Regression.")
    def linear_regression(X: List[List[float]], y: List[float]) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_linear_regression.

        Args:
            X: Feature matrix as list of lists (rows=samples, columns=features).
            y: Target values as a flat list.

        Returns:
            Dict with 'coefficients', 'intercept', and 'score_r2'.
        """
        return calculate_linear_regression(X, y)

    @mcp.tool(name="ridge_regression", description="Calculates Ridge Regression (L2 regularization).")
    def ridge_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_ridge_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            alpha: Regularization strength (higher = more shrinkage).

        Returns:
            Dict with 'coefficients', 'intercept', and 'score_r2'.
        """
        return calculate_ridge_regression(X, y, alpha=alpha)

    @mcp.tool(name="lasso_regression", description="Calculates Lasso Regression (L1 regularization).")
    def lasso_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_lasso_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            alpha: Regularization strength (higher = more features zeroed out).

        Returns:
            Dict with 'coefficients', 'intercept', and 'score_r2'.
        """
        return calculate_lasso_regression(X, y, alpha=alpha)

    @mcp.tool(name="polynomial_regression", description="Calculates Polynomial Regression of a given degree.")
    def polynomial_regression(X: List[List[float]], y: List[float], degree: int = 2) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_polynomial_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            degree: Degree of the polynomial features to generate.

        Returns:
            Dict with 'degree', 'coefficients', 'intercept', and 'score_r2'.
        """
        return calculate_polynomial_regression(X, y, degree=degree)

    @mcp.tool(name="nonlinear_regression", description="Calculates Nonlinear Regression for a given model function string.")
    def nonlinear_regression(X: List[float], y: List[float], model_func_str: str, p0: List[float] = None) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_nonlinear_regression.

        Evaluates the model_func_str into a callable Python expression before
        passing it to the underlying regression function.

        Args:
            X: Feature values as a flat list (single-feature nonlinear regression).
            y: Target values as a flat list.
            model_func_str: Lambda string, e.g. 'lambda x, a, b: a * np.exp(b * x)'.
            p0: Initial guess for the parameters (optional).

        Returns:
            Dict with 'parameters', 'covariance', and 'score_r2'.
        """
        import numpy as np
        # Parse the lambda string into an actual callable using eval with numpy namespace
        model_func = eval(model_func_str, {"np": np})
        return calculate_nonlinear_regression(X, y, model_func, p0=p0)

    @mcp.tool(name="support_vector_regression", description="Calculates Support Vector Regression.")
    def support_vector_regression(X: List[List[float]], y: List[float], kernel: str = 'rbf', C: float = 1.0, epsilon: float = 0.1) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_support_vector_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            kernel: Kernel function type ('linear', 'poly', 'rbf', 'sigmoid').
            C: Regularization parameter (higher = less regularization).
            epsilon: Width of the epsilon-insensitive loss tube.

        Returns:
            Dict with 'kernel', 'score_r2', and 'params' (C, epsilon).
        """
        return calculate_support_vector_regression(X, y, kernel=kernel, C=C, epsilon=epsilon)

    @mcp.tool(name="decision_tree_regression", description="Calculates Decision Tree Regression.")
    def decision_tree_regression(X: List[List[float]], y: List[float], max_depth: int = None) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_decision_tree_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            max_depth: Maximum depth of the tree (None = unlimited).

        Returns:
            Dict with 'max_depth', 'score_r2', and 'feature_importances'.
        """
        return calculate_decision_tree_regression(X, y, max_depth=max_depth)

    @mcp.tool(name="random_forest_regression", description="Calculates Random Forest Regression.")
    def random_forest_regression(X: List[List[float]], y: List[float], n_estimators: int = 100, max_depth: int = None) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_random_forest_regression.

        Args:
            X: Feature matrix as list of lists.
            y: Target values as a flat list.
            n_estimators: Number of trees in the forest.
            max_depth: Maximum depth of each tree (None = unlimited).

        Returns:
            Dict with 'n_estimators', 'max_depth', 'score_r2', and 'feature_importances'.
        """
        return calculate_random_forest_regression(X, y, n_estimators=n_estimators, max_depth=max_depth)

    @mcp.tool(name="logistic_regression", description="Calculates Logistic Regression for classification tasks.")
    def logistic_regression(X: List[List[float]], y: List[int], C: float = 1.0) -> Dict[str, Any]:
        """
        Wrapper tool for calculate_logistic_regression.

        NOTE: This is a classification method, not regression. It returns accuracy
        and predicted class labels instead of R-squared and a continuous intercept.

        Args:
            X: Feature matrix as list of lists.
            y: Class labels as a flat list of integers.
            C: Inverse regularization strength (higher = less regularization).

        Returns:
            Dict with 'coefficients', 'intercept', 'score_accuracy', and 'classes'.
        """
        return calculate_logistic_regression(X, y, C=C)

    if registry is not None:
        # Register the module API dictionary so other parts of the application
        # can look up available statistical methods by name.
        registry.register_module_api("StatisticalMethods", get_module_api())
