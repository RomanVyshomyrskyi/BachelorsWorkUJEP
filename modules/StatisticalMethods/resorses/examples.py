# Examples of using regression methods

# 1. Linear Regression
# X: [[x1_1, x1_2, ...], [x2_1, x2_2, ...], ...]
# y: [y1, y2, ...]
# result = linear_regression(X=[[1], [2], [3], [4], [5]], y=[2, 4, 6, 8, 10])

# 2. Polynomial Regression
# result = polynomial_regression(X=[[1], [2], [3]], y=[1, 4, 9], degree=2)

# 3. Ridge Regression
# result = ridge_regression(X=[[1], [2]], y=[10, 20], alpha=0.5)

# 4. Lasso Regression
# result = lasso_regression(X=[[1, 2], [2, 1], [3, 4]], y=[1, 2, 3], alpha=0.1)

# 5. Nonlinear Regression
# model_func_str = "lambda x, a, b: a * np.exp(b * x)"
# result = nonlinear_regression(X=[1, 2, 3, 4, 5], y=[2.7, 7.4, 20.1, 54.6, 148.4], model_func_str=model_func_str)

# 6. Support Vector Regression
# result = support_vector_regression(X=[[1], [2], [3]], y=[1.1, 1.9, 3.2], kernel='rbf', C=100.0)

# 7. Decision Tree Regression
# result = decision_tree_regression(X=[[1], [2], [3]], y=[10, 20, 30], max_depth=5)

# 8. Random Forest Regression
# result = random_forest_regression(X=[[1], [2], [3]], y=[10, 20, 30], n_estimators=100)

# 9. Logistic Regression
# result = logistic_regression(X=[[1, 2], [2, 3], [5, 6], [7, 8]], y=[0, 0, 1, 1])
