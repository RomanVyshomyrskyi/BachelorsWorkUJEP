# Statistical Methods Module

This module provides tools for performing various statistical regression analyses, ranging from simple linear regression to complex ensemble methods like random forests.

---

## User Documentation

### Features
- Simple and Multiple Linear Regression.
- Regularized Regression (Ridge and Lasso).
- Polynomial and Nonlinear Regression.
- Support Vector Regression (SVR).
- Decision Tree and Random Forest Regression.
- Logistic Regression for classification tasks.

### Available Tools (MCP)
- `linear_regression(X, y)`: Calculates Simple and Multiple Linear Regression.
- `ridge_regression(X, y, alpha)`: Calculates Ridge Regression (L2 regularization).
- `lasso_regression(X, y, alpha)`: Calculates Lasso Regression (L1 regularization).
- `polynomial_regression(X, y, degree)`: Calculates Polynomial Regression of a given degree.
- `nonlinear_regression(X, y, model_func_str, p0)`: Calculates Nonlinear Regression for a given model function (string format).
- `support_vector_regression(X, y, kernel, C, epsilon)`: Calculates Support Vector Regression.
- `decision_tree_regression(X, y, max_depth)`: Calculates Decision Tree Regression.
- `random_forest_regression(X, y, n_estimators, max_depth)`: Calculates Random Forest Regression.
- `logistic_regression(X, y, C)`: Calculates Logistic Regression for classification.

### Example Usage
Refer to `modules/StatisticalMethods/resorses/examples.py` for Python snippets demonstrating how to call each method.

---

## Developer Documentation

### Architecture
- **`regression/`**: Contains the core logic for each regression type (linear, logistic, nonlinear, etc.) using `scikit-learn`, `numpy`, and `scipy`.
- **`resorses/explanations.md`**: Provides the mathematical background for each method.
- **`resorses/methods/`**: Detailed documentation for the implementation of each regression technique.
- **`main.py`**: Registers all tools with the FastMCP instance and maps them to functions in `regression/`.

### Adding a New Method
To add a new statistical method:
1. Create a new `.py` file in `modules/StatisticalMethods/regression/` or add to an existing one.
2. Implement the calculation logic (typically returning a dictionary with results and scores).
3. Import the new function in `main.py`.
4. Register a new MCP tool in `main.py`'s `register()` function.
5. Update `resorses/explanations.md` and add an example to `resorses/examples.py`.

### Local Development
Install dependencies listed in `modules/StatisticalMethods/requirements.txt`:
```bash
pip install -r modules/StatisticalMethods/requirements.txt
```

---

## Cross-Module Interface

### Dependency Declaration
`depends_on = []` — this module has no dependencies on other modules.

### Public API (`get_module_api()`)
Other modules can access all regression functions via the `ModuleRegistry`:
- `linear_regression`, `ridge_regression`, `lasso_regression`
- `polynomial_regression`, `nonlinear_regression`
- `support_vector_regression`, `decision_tree_regression`
- `random_forest_regression`, `logistic_regression`

### Usage from another module
```python
depends_on = ["StatisticalMethods"]

def register(mcp, registry=None):
    if registry:
        stats_api = registry.get_module_api("StatisticalMethods")
        result = stats_api["linear_regression"](X, y)
```
