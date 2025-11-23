# Guide to Database Normalization (1NF, 2NF, 3NF)

This document provides a set of rules and guidelines for understanding the first three normal forms (1NF, 2NF, 3NF). This can be used as a knowledge base to analyze a given database schema and provide suggestions for normalization.

---

## First Normal Form (1NF)

**Objective:** Ensure that a table is a "flat" table with no repeating groups. Each cell should hold a single, atomic value, and each record should be unique.

**Rules:**

1.  **Atomicity**: Each column must hold a single, indivisible value. A column cannot contain a list, array, or set of values.
    *   **Violation Example**: A `phone_numbers` column containing '555-1234, 555-5678'.
    *   **Correction**: Create a separate `PhoneNumbers` table with a foreign key back to the original table. Each phone number gets its own row.

2.  **No Repeating Groups**: There should be no groups of related data in the same table.
    *   **Violation Example**: Columns named `child1_name`, `child2_name`, `child3_name`.
    *   **Correction**: Create a separate `Children` table with a foreign key. Each child gets their own row.

3.  **Primary Key**: The table must have a primary key that uniquely identifies each row. This can be a single column or a composite key (multiple columns).

**Example Analysis:**

*   **Given Table:** `EMPLOYEE` (EmployeeID, Name, PhoneNumbers)
*   **Analysis:** This table violates 1NF because the `PhoneNumbers` column might contain multiple values (e.g., "work, home").
*   **Suggestion:** Create two tables:
    *   `EMPLOYEE` (EmployeeID (PK), Name)
    *   `EMPLOYEE_PHONE` (PhoneID (PK), EmployeeID (FK), PhoneNumber)

---

## Second Normal Form (2NF)

**Prerequisite:** The table must already be in 1NF.

**Objective:** Eliminate partial dependencies. All non-key attributes must be fully functionally dependent on the *entire* primary key. This rule only applies to tables with a **composite primary key** (a primary key made of two or more columns).

**Rules:**

1.  **Be in 1NF**: The table must satisfy all rules of 1NF.
2.  **No Partial Dependencies**: Every non-key column must depend on the whole composite primary key, not just a part of it.
    *   **Violation Example**: A table `ORDER_ITEMS` with a composite primary key (OrderID, ProductID) and columns `Quantity`, `ProductName`, `OrderDate`.
        *   `Quantity` depends on both `OrderID` and `ProductID` (Correct).
        *   `ProductName` depends only on `ProductID` (Partial dependency violation).
        *   `OrderDate` depends only on `OrderID` (Partial dependency violation).
    *   **Correction**: Decompose the table into smaller tables that each have a single purpose.
        *   `ORDERS` (OrderID (PK), OrderDate)
        *   `PRODUCTS` (ProductID (PK), ProductName)
        *   `ORDER_ITEMS` (OrderID (FK), ProductID (FK), Quantity)

**Example Analysis:**

*   **Given Table:** `PROJECT_ASSIGNMENTS` (EmployeeID (PK), ProjectID (PK), EmployeeName, ProjectName)
*   **Analysis:** This table violates 2NF. `EmployeeName` depends only on `EmployeeID`, and `ProjectName` depends only on `ProjectID`. These are partial dependencies.
*   **Suggestion:** Create three tables:
    *   `EMPLOYEES` (EmployeeID (PK), EmployeeName)
    *   `PROJECTS` (ProjectID (PK), ProjectName)
    *   `PROJECT_ASSIGNMENTS` (EmployeeID (FK), ProjectID (FK))

---

## Third Normal Form (3NF)

**Prerequisite:** The table must already be in 2NF.

**Objective:** Eliminate transitive dependencies. All attributes must be dependent *only* on the primary key, not on other non-key attributes.

**Rules:**

1.  **Be in 2NF**: The table must satisfy all rules of 2NF.
2.  **No Transitive Dependencies**: No non-key attribute should be dependent on another non-key attribute. A transitive dependency is an indirect relationship between values in the same table.
    *   **Violation Example**: A table `EMPLOYEES` (EmployeeID (PK), Name, DepartmentID, DepartmentName, DepartmentLocation).
        *   `DepartmentName` and `DepartmentLocation` depend on `DepartmentID` (a non-key attribute).
        *   Since `DepartmentID` depends on `EmployeeID`, this creates a transitive dependency: `EmployeeID` -> `DepartmentID` -> `DepartmentName`.
    *   **Correction**: Move the transitively dependent columns into their own table.
        *   `EMPLOYEES` (EmployeeID (PK), Name, DepartmentID (FK))
        *   `DEPARTMENTS` (DepartmentID (PK), DepartmentName, DepartmentLocation)

**Example Analysis:**

*   **Given Table:** `BOOKS` (BookID (PK), Title, AuthorID, AuthorName, AuthorBio)
*   **Analysis:** This table violates 3NF. `AuthorName` and `AuthorBio` are dependent on `AuthorID`, which is a non-key attribute.
*   **Suggestion:** Decompose into two tables:
    *   `BOOKS` (BookID (PK), Title, AuthorID (FK))
    *   `AUTHORS` (AuthorID (PK), AuthorName, AuthorBio)
