# DBAnalysis Module

This module provides tools to analyze relational database schemas for normalization compliance and perform data visualization.

---

## Detailed Functionality Reference

### Analysis Tools (`tools/analysis.py`)

#### `get_normalization_rules()`
- **What it does**: Retrieves the text content of the database normalization standards (1NF, 2NF, 3NF).
- **How it does it**: Uses `utils/rules_loader.py` to locate and read `normalization_rules.md` from the module's root directory.

#### `analyze_database_schema(db_type, host, user, password, dbname, port)`
- **What it does**: Gathers all necessary context (rules + schema) for an AI-driven normalization analysis.
- **How it does it**:
    1. Uses `strategies/factory.py` to instantiate the correct `DatabaseStrategy` (Postgres, MariaDB, or MSSQL).
    2. Opens a connection context manager which handles `connect()` and `disconnect()`.
    3. Calls `get_schema_representation()` on the strategy, which executes system-specific SQL queries against `information_schema`.
    4. Merges the schema string with the normalization rules and returns a formatted prompt for an LLM.

### Data Tools (`tools/data.py`)

#### `run_read_only_sql(db_type, host, user, password, dbname, query, port)`
- **What it does**: Safely executes a SELECT query and returns the data.
- **How it does it**:
    1. Validates that the query starts with `SELECT` (basic security check).
    2. Uses the database-specific strategy to execute the raw SQL.
    3. Converts the resulting rows (tuples) into a list of dictionaries mapping column names to values.

#### `get_table_data(db_type, host, user, password, dbname, table_name, limit, port)`
- **What it does**: Quickly previews data from a specific table.
- **How it does it**:
    1. Constructs a `SELECT * FROM {table} LIMIT {limit}` query (or `TOP` for MSSQL).
    2. Reuses the `run_read_only_sql` logic via the strategy's `execute_query` method.

### Visualization Tools (`tools/visualization.py`)

#### `generate_database_chart(...)`
- **What it does**: Transforms SQL query results into a visual chart (PNG).
- **How it does it**:
    1. Fetches data using the selected `DatabaseStrategy`.
    2. Loads the result list into a **Pandas DataFrame**.
    3. Uses **Matplotlib** (with the non-interactive `Agg` backend) to create a figure.
    4. Depending on `chart_type`, calls `plt.bar`, `plt.plot`, `plt.scatter`, or `plt.pie`.
    5. Saves the plot to a `BytesIO` buffer, encodes it to **Base64**, and returns it as a rich MCP content object.

---

## Developer Documentation: Internal Logic

### Database Strategies (`strategies/`)
The module implements the **Strategy Pattern** to abstract away dialect differences:
- **`DatabaseStrategy` (Base)**: Defines the interface. Uses `__enter__` and `__exit__` to ensure connections are always closed.
- **`PostgresStrategy`**: Uses `psycopg2`. Queries `public` schema for tables and handles PostgreSQL-specific foreign key joins in `information_schema`.
- **`MariaDBStrategy`**: Uses `mysql.connector`. Queries `TABLE_SCHEMA` based on the provided database name.
- **`MSSQLStrategy`**: Uses `pyodbc`. Requires "ODBC Driver 17 for SQL Server". Queries `TABLE_CATALOG` and handles the complex multi-join relationship queries required by SQL Server.

### Utilities (`utils/`)
- **`formatters.py`**: Contains `format_schema`, which iterates through table/column rows and foreign key relationships to build a structured, human-readable string representation of the DB.
- **`rules_loader.py`**: Handles absolute path resolution for reading the markdown knowledge base.

---

## Cross-Module Interface

### Dependency Declaration
`depends_on = []` — this module has no dependencies on other modules.

### Public API (`get_module_api()`)
Other modules can access these functions via the `ModuleRegistry`:
- `get_db_strategy` — creates a database-specific strategy instance
- `get_normalization_rules` — retrieves normalization rules text

### Usage from another module
```python
depends_on = ["DBAnalysis"]

def register(mcp, registry=None):
    if registry:
        db_api = registry.get_module_api("DBAnalysis")
        strategy = db_api["get_db_strategy"](db_type, host, user, password, dbname, port)
```
