# DBAnalysis Module

This module provides tools to analyze the schema of a relational database for compliance with the first three normal forms (1NF, 2NF, 3NF).

It uses a **Strategy Design Pattern** to support analysis for multiple database systems (PostgreSQL, MariaDB, and MSSQL) and leverages a knowledge base (`normalization_rules.md`) to provide context for AI-driven suggestions.

---

## Endpoints

### `POST /DBAnalysis/analyze`

This is the primary endpoint for performing a database analysis. It connects to the specified database, extracts its schema, and then simulates generating normalization suggestions.

**Request Body:**

```json
{
  "db_type": "postgres",
  "connection_details": {
    "host": "your_db_host",
    "user": "your_db_user",
    "password": "your_db_password",
    "dbname": "your_database_name",
    "port": 5432
  }
}
```

*   **`db_type`**: The type of database to analyze. Must be one of `postgres`, `mariadb`, or `mssql`.
*   **`connection_details`**: A dictionary containing the credentials and information needed to connect to the database.

**Response:**

The endpoint returns a JSON object containing the simulated analysis and the full prompt that would be sent to an LLM for generating suggestions.

### `GET /DBAnalysis/rules`

A simple endpoint to retrieve the contents of the `normalization_rules.md` file used by the analyzer.

---

## Architecture

This module uses a **Strategy Pattern** to cleanly separate the analysis logic for different database systems.

1.  **`interfaces.py`**: Defines the `DatabaseStrategy` abstract base class, which requires all concrete strategies to implement methods like `connect()`, `disconnect()`, and `get_schema_representation()`.
2.  **`strategies.py`**: Provides the concrete implementations: `PostgresStrategy`, `MariaDBStrategy`, and `MSSQLStrategy`. Each class contains the specific SQL queries and logic needed to extract the schema from its target database.
3.  **`main.py`**: The API endpoint uses a factory function (`get_db_strategy`) to select the correct strategy at runtime based on the `db_type` provided in the request.

This pattern makes it easy to extend the module to support other database systems in the future by simply adding a new strategy class.

---

## Local Development

This module has its own Python dependencies, which are listed in `modules/DBAnalysis/requirements.txt`.

To run the application in a local development environment (outside of Docker), you must install these dependencies into your virtual environment:

```bash
pip install -r modules/DBAnalysis/requirements.txt
```
