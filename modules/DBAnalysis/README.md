# DBAnalysis Module

This module provides tools to analyze relational database schemas for normalization compliance, execute read-only SQL queries, preview table data, and generate charts from database results.

---

## Quick Start

Run the full Docker Compose environment (PostgreSQL, MariaDB, MSSQL + FastMCP server):

```bash
docker-compose up --build
```

Credentials are managed in `.env`. See [Working with Docker Test Databases](#working-with-docker-test-databases) below for details.

---

## Configuring Database Connections

You can connect to a database in two ways:

### 1. Pre-configured via `databases.json` (use `db_id`)

Edit `modules/DBAnalysis/databases.json` (copy from `databases.json.example` if needed):

```json
{
  "my_mariadb": {
    "db_type": "mariadb",
    "host": "localhost",
    "port": 3306,
    "dbname": "my_database",
    "user": "my_user",
    "password": "my_password"
  },
  "analytics_postgres": {
    "db_type": "postgres",
    "host": "pg.example.com",
    "port": 5432,
    "dbname": "analytics",
    "user": "reader",
    "password_env": "PG_PASSWORD"
  }
}
```

Then reference it by `db_id` in any tool call (the `password` is resolved from the JSON, or from the env var named in `password_env`):

```
analyze_database_schema(db_id="analytics_postgres")
```

### 2. Inline connection parameters (no config file needed)

Every tool accepts direct connection parameters. No `databases.json` entry required:

```
analyze_database_schema(
  db_type="postgres",
  host="localhost",
  port=5432,
  dbname="my_db",
  user="admin",
  password="secret"
)
```

### Password from Environment Variables

Use `password_env` in `databases.json` to avoid hardcoding secrets:

```json
{
  "my_db": {
    "db_type": "postgres",
    "host": "localhost",
    "port": 5432,
    "dbname": "mydb",
    "user": "admin",
    "password_env": "MY_DB_PASSWORD"
  }
}
```

The module calls `os.getenv("MY_DB_PASSWORD")` at runtime. If the env var is not set and no fallback `password` is provided, a warning is logged.

---

## Available Tools

| MCP Tool | Description |
|---|---|
| `get_normalization_rules` | Returns the database normalization rules (1NF, 2NF, 3NF) |
| `analyze_database_schema` | Extracts full schema + normalization rules for AI analysis |
| `run_read_only_sql` | Safely executes `SELECT` queries and returns JSON results |
| `get_table_data` | Previews rows from a specific table (with safety limit) |
| `generate_database_chart` | Runs a query and returns a PNG bar/line/scatter/pie chart |

Every tool (except `get_normalization_rules`) accepts either `db_id` or the full set of connection fields (`db_type`, `host`, `user`, `password`, `dbname`, `port`).

---

## Usage Examples

### Analyze a database schema for normalization compliance

```json
{
  "name": "analyze_database_schema",
  "arguments": {
    "db_id": "analytics_postgres"
  }
}
```

### Run a read-only SQL query

```json
{
  "name": "run_read_only_sql",
  "arguments": {
    "query": "SELECT table_name, table_rows FROM information_schema.tables WHERE table_schema = 'public'",
    "db_id": "analytics_postgres"
  }
}
```

### Preview table data

```json
{
  "name": "get_table_data",
  "arguments": {
    "table_name": "users",
    "db_id": "analytics_postgres",
    "limit": 50
  }
}
```

### Generate a chart

```json
{
  "name": "generate_database_chart",
  "arguments": {
    "query": "SELECT category, COUNT(*) as count FROM products GROUP BY category",
    "chart_type": "bar",
    "x_column": "category",
    "y_column": "count",
    "title": "Products by Category",
    "db_id": "analytics_postgres"
  }
}
```

### Connect inline (no config file)

```json
{
  "name": "run_read_only_sql",
  "arguments": {
    "db_type": "postgres",
    "host": "localhost",
    "port": 5432,
    "dbname": "Postgres_Test_DB",
    "user": "admin",
    "password": "admin",
    "query": "SELECT current_database()"
  }
}
```

---

## Supported Database Types

### Direct Database Connections

| db_type | Driver | Default Port | Docker Image | System Requirements |
|---------|--------|--------------|--------------|---------------------|
| `postgres` | `psycopg2` | 5432 | `postgres:14-alpine` | `libpq-dev` |
| `mariadb` | `mysql.connector` | 3306 | `mariadb:10.8` | None (pure Python) |
| `mysql` | `mysql.connector` | 3306 | `mariadb:10.8` | None (pure Python) |
| `mssql` | `pyodbc` | 1433 | `mcr.microsoft.com/mssql/server:2019-latest` | ODBC Driver 17 for SQL Server, `unixodbc-dev` |

**Security Features:**
- All queries are validated using `sqlparse` AST parsing to block write operations (INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
- Multi-statement queries are blocked (prevents `SELECT 1; DROP TABLE users`)
- Stored procedures with `sp_` and `xp_` prefixes are blocked
- Row limits enforced: 1000 rows for SQL queries, 100 rows for table previews
- Query timeout: 30 seconds per query
- Error messages are sanitized to prevent schema/DB info leakage

---

### Indirect Database Access via Superset

The `SupersetModule` communicates with any database backend supported by **Apache Superset** via HTTP API. This includes:
- PostgreSQL
- MySQL / MariaDB
- Microsoft SQL Server
- And any other database configured in your Superset instance

See the [SupersetModule README](../SupersetModule/README.md) for details.

---

## Working with Docker Test Databases

The project's `docker-compose.yml` launches three test databases. Credentials are set in `.env`:

| Service | Image | Container Name | Internal Host | `.env` User | `.env` Password | `.env` Database |
|---------|-------|---------------|---------------|-------------|-----------------|-----------------|
| `postgres-db` | `postgres:14-alpine` | `postgres-test-db` | `postgres-db` | `POSTGRES_USER` | `POSTGRES_PASSWORD` | `POSTGRES_DB` |
| `mariadb-db` | `mariadb:10.8` | `mariadb-test-db` | `mariadb-db` | `root` | `MARIADB_ROOT_PASSWORD` | `MARIADB_DATABASE` |
| `mssql-db` | `mcr.microsoft.com/mssql/server:2019-latest` | `mssql-test-db` | `mssql-db` | `sa` | `MSSQL_SA_PASSWORD` | (none, use `sa` as user) |

**Important:** The hostnames to use from inside the Docker network are the service names (e.g., `postgres-db`, `mariadb-db`, `mssql-db`), not `localhost`. From outside Docker (your host machine), use `localhost` and the mapped ports (5432, 3306, 1433).

### System Dependencies (for non-Docker installs)

To run database drivers without Docker, install these system packages:

| Database | Package |
|----------|---------|
| PostgreSQL | `libpq-dev` |
| MSSQL | `unixodbc-dev`, ODBC Driver 17 for SQL Server |
| MariaDB/MySQL | None (pure Python driver) |

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
    1. Validates the query using `sqlparse` AST parsing to ensure it's read-only (blocks INSERT, UPDATE, DELETE, DROP, ALTER, etc.)
    2. Blocks multi-statement queries and dangerous stored procedures (`sp_`, `xp_`)
    3. Enforces a 30-second timeout and 1000-row limit
    4. Uses the database-specific strategy to execute the raw SQL
    5. Converts the resulting rows into a list of dictionaries mapping column names to values

#### `get_table_data(db_type, host, user, password, dbname, table_name, limit, port)`
- **What it does**: Quickly previews data from a specific table.
- **How it does it**:
    1. Validates the table name format to prevent injection
    2. Clamps the limit to 100 rows maximum
    3. Constructs a `SELECT * FROM {table} LIMIT {limit}` query (or `TOP` for MSSQL)
    4. Reuses the strategy's `execute_query` method with the same security validation

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
