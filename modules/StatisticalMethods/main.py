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

def get_module_api():
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
    @mcp.tool(name="test", description="rest registration")
    def test():
        return "Statistical Methods module registered successfully!"

    @mcp.tool(name="linear_regression", description="Calculates Simple and Multiple Linear Regression.")
    def linear_regression(X: List[List[float]], y: List[float]) -> Dict[str, Any]:
        return calculate_linear_regression(X, y)

    @mcp.tool(name="ridge_regression", description="Calculates Ridge Regression (L2 regularization).")
    def ridge_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
        return calculate_ridge_regression(X, y, alpha=alpha)

    @mcp.tool(name="lasso_regression", description="Calculates Lasso Regression (L1 regularization).")
    def lasso_regression(X: List[List[float]], y: List[float], alpha: float = 1.0) -> Dict[str, Any]:
        return calculate_lasso_regression(X, y, alpha=alpha)

    @mcp.tool(name="polynomial_regression", description="Calculates Polynomial Regression of a given degree.")
    def polynomial_regression(X: List[List[float]], y: List[float], degree: int = 2) -> Dict[str, Any]:
        return calculate_polynomial_regression(X, y, degree=degree)

    @mcp.tool(name="nonlinear_regression", description="Calculates Nonlinear Regression for a given model function string (e.g., 'lambda x, a, b: a * np.exp(b * x)').")
    def nonlinear_regression(X: List[float], y: List[float], model_func_str: str, p0: List[float] = None) -> Dict[str, Any]:
        import numpy as np
        model_func = eval(model_func_str, {"np": np})
        return calculate_nonlinear_regression(X, y, model_func, p0=p0)

    @mcp.tool(name="support_vector_regression", description="Calculates Support Vector Regression.")
    def support_vector_regression(X: List[List[float]], y: List[float], kernel: str = 'rbf', C: float = 1.0, epsilon: float = 0.1) -> Dict[str, Any]:
        return calculate_support_vector_regression(X, y, kernel=kernel, C=C, epsilon=epsilon)

    @mcp.tool(name="decision_tree_regression", description="Calculates Decision Tree Regression.")
    def decision_tree_regression(X: List[List[float]], y: List[float], max_depth: int = None) -> Dict[str, Any]:
        return calculate_decision_tree_regression(X, y, max_depth=max_depth)

    @mcp.tool(name="random_forest_regression", description="Calculates Random Forest Regression.")
    def random_forest_regression(X: List[List[float]], y: List[float], n_estimators: int = 100, max_depth: int = None) -> Dict[str, Any]:
        return calculate_random_forest_regression(X, y, n_estimators=n_estimators, max_depth=max_depth)

    @mcp.tool(name="logistic_regression", description="Calculates Logistic Regression for classification tasks.")
    def logistic_regression(X: List[List[float]], y: List[int], C: float = 1.0) -> Dict[str, Any]:
        return calculate_logistic_regression(X, y, C=C)

    if registry is not None:
        registry.register_module_api("StatisticalMethods", get_module_api())
