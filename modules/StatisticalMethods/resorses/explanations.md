# Regression Methods - Explanations

## 1. Linear Regression (Lineární regrese)
Linear regression models the relationship between a dependent variable $y$ and one or more independent variables $X$.
- **Simple Linear Regression:** $y = \beta_0 + \beta_1 x + \epsilon$
- **Multiple Linear Regression:** $y = \beta_0 + \beta_1 x_1 + \beta_2 x_2 + ... + \beta_n x_n + \epsilon$
- **How it works:** It uses Ordinary Least Squares (OLS) to minimize the sum of squared differences between observed and predicted values.

## 2. Polynomial Regression (Polynomiální regrese)
A form of regression where the relationship between the independent variable $x$ and the dependent variable $y$ is modeled as an $n$-th degree polynomial.
- **Formula:** $y = \beta_0 + \beta_1 x + \beta_2 x^2 + ... + \beta_n x^n + \epsilon$
- **How it works:** It transforms the original features into polynomial features and then applies linear regression.

## 3. Nonlinear Regression (Nelineární regrese)
Models observational data by a function which is a nonlinear combination of the model parameters.
- **Formula:** $y = f(x, \beta) + \epsilon$
- **How it works:** Uses iterative optimization algorithms (like Levenberg-Marquardt) to find parameters that minimize the sum of squares.

## 4. Support Vector Regression (SVR)
A version of Support Vector Machines (SVM) used for regression.
- **Goal:** To find a function $f(x)$ that has at most $\epsilon$ deviation from the actually obtained targets $y_i$ for all the training data, and at the same time is as flat as possible.
- **How it works:** It uses kernels to map data into high-dimensional space where linear regression is performed.

## 5. Decision Tree Regression
Uses a decision tree to go from observations about an item to conclusions about the item's target value.
- **How it works:** Splits the data into subsets based on feature values, minimizing the variance (or Mean Squared Error) in each leaf.

## 6. Random Forest Regression
An ensemble learning method that operates by constructing a multitude of decision trees at training time.
- **How it works:** It outputs the average prediction of the individual trees. This helps reduce overfitting.

## 7. Ridge Regression
A technique used when the data suffers from multicollinearity.
- **Formula:** Minimizes $	ext{RSS} + \alpha \sum_{j=1}^n \beta_j^2$
- **How it works:** Adds an L2 penalty term (squared magnitude of coefficients) to the loss function.

## 8. Lasso Regression (Least Absolute Shrinkage and Selection Operator)
- **Formula:** Minimizes $	ext{RSS} + \alpha \sum_{j=1}^n |\beta_j|$
- **How it works:** Adds an L1 penalty term (absolute value of coefficients). It can lead to sparse models where some coefficients are exactly zero.

## 9. Logistic Regression (Logistická regrese)
Used for classification, not regression in the standard sense, but it uses a regression-like linear combination.
- **Formula:** $p = \frac{1}{1 + e^{-(\beta_0 + \beta_1 x_1 + ...)}}$
- **How it works:** Maps the output of a linear equation to a probability between 0 and 1 using the sigmoid function.
