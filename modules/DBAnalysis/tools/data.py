"""
Data Tools - Read-only database query and data retrieval MCP tools.

Provides MCP tools for executing raw SQL SELECT queries and fetching
table data from PostgreSQL, MariaDB/MySQL, and Microsoft SQL Server
databases. All tools enforce read-only access and include input validation.
"""

import json
import re
import time
from typing import Optional, Literal
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..db_manager import DbManager
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

# Regular expression pattern for validating SQL identifiers (table names)
# Must start with a letter or underscore, followed by alphanumeric characters or underscores
# Supports optional schema qualification (e.g., "schema.table_name")
_IDENTIFIER_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*(\.[a-zA-Z_][a-zA-Z0-9_]*)?$')


def _validate_identifier(name: str) -> str:
    """
    Validate that a table name is a safe SQL identifier.

    This prevents SQL injection through table names by ensuring the name
    matches the expected identifier pattern (alphanumeric + underscores).

    Args:
        name: The table name string to validate.

    Returns:
        The validated table name if it matches the expected pattern.

    Raises:
        ValueError: If the table name contains invalid characters.
    """
    # Check if the table name matches the allowed identifier pattern
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid table name: '{name}'")
    return name


def _sanitize_error(e: Exception) -> str:
    """
    Return a generic, non-disclosing error message for MCP clients.

    Internal error details (stack traces, connection strings, query text)
    are logged server-side while the user receives a generic message.

    Args:
        e: The exception that occurred during query execution.

    Returns:
        A generic error message string that does not leak sensitive information.
    """
    # Log the actual error details for server-side debugging
    logger = LogCollector(f"data.error").error
    logger(f"Internal error: {e}")
    return "An error occurred while processing your request. Please try again."


def _resolve_config(
    db_manager: Optional[DbManager],
    db_id: Optional[str],
    db_type: Optional[str],
    host: Optional[str],
    user: Optional[str],
    password: Optional[str],
    dbname: Optional[str],
    port: Optional[int],
) -> dict:
    """
    Resolve database connection configuration from either a db_id or individual fields.

    This helper determines connection parameters by either looking up a
    pre-configured database by ID, or by assembling them from individual
    parameters provided directly in the tool call.

    Args:
        db_manager: The DbManager instance for looking up configurations by ID.
        db_id: Optional database ID to look up in the configuration file.
        db_type: Database type (postgres, mariadb, mysql, mssql).
        host: Database host address.
        user: Database username.
        password: Database password.
        dbname: Database name.
        port: Database port (optional; defaults will be used if 0 or None).

    Returns:
        A dictionary with keys: db_type, host, port, dbname, user, password.
        1. If db_id is provided, look up the config in DbManager and return it.
        2. If no db_id, require all of db_type, host, user, dbname to be provided.
        3. Resolve the port using the default if not specified.
        4. Return the assembled configuration dictionary.

    Raises:
        ValueError: If db_id is provided without a db_manager, or if neither
                    db_id nor all required individual fields are provided.
    """
    # If a database ID is provided, look up the configuration from DbManager
    if db_id:
        # Ensure a database manager is available for configuration lookup
        if db_manager is None:
            raise ValueError("db_id provided but no database manager available")
        # Retrieve the configuration dictionary for this database ID
        cfg = db_manager.get_config(db_id)
        # Return an error if the database ID doesn't exist in the config
        if not cfg:
            raise ValueError(f"Database '{db_id}' not found in configuration")
        return cfg

    # If no db_id, validate that all required individual fields are provided
    if not db_type or not host or not user or not dbname:
        raise ValueError("Either db_id or all of db_type, host, user, dbname must be provided")

    # Assemble the configuration from individual parameters
    return {
        "db_type": db_type,
        "host": host,
        # Use provided port or resolve the default for the database type
        "port": port or _default_port(db_type),
        "dbname": dbname,
        "user": user,
        # Use provided password or default to empty string
        "password": password or "",
    }


def _default_port(db_type: str) -> int:
    """
    Return the default port for a given database type.

    Args:
        db_type: The database type string (e.g., "postgres", "mariadb", "mysql", "mssql").

    Returns:
        The default port number as an integer.
    """
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)


def tool_run_sql(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    query: str,
    port: int = 0
) -> str:
    """
    MCP tool for executing a read-only SQL query against a database.

    This tool connects to a specified database, executes a SELECT query
    with read-only validation, and returns the results as a JSON string.
    Only SELECT and WITH (CTE) queries are allowed.

    Args:
        db_type: Type of database to connect to (postgres, mariadb, mysql, mssql).
        host: Database server hostname or IP address.
        user: Database username for authentication.
        password: Database password for authentication.
        dbname: Name of the database to query.
        query: SQL SELECT query to execute (must be read-only).
        port: Database port number (0 = use default for db_type).

    Returns:
        A JSON string containing the query results as a list of dictionaries,
        or an error message string if the query fails.
        1. Resolves the default port if not explicitly provided.
        2. Creates a ConnectionDetails object and gets the appropriate strategy.
        3. Opens a database context manager (connect -> execute -> disconnect).
        4. Executes the validated read-only query and fetches results.
        5. Returns results as a JSON string.
    """
    # Initialize the log collector for tracking tool operations
    log = LogCollector(f"{__name__}.run_sql")

    # Resolve the default port if not explicitly provided (port=0 means use default)
    if not port:
        port = _default_port(db_type)

    try:
        # Log the query execution request with database connection details
        log.info(f"Executing query on {db_type}://{host}:{port}/{dbname}")

        # Create a ConnectionDetails Pydantic model to hold connection parameters
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )

        # Get the appropriate database strategy based on db_type and connection details
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        # Open a database context manager: connects, executes query, then disconnects
        with strategy as db_context:
            # Log the query (truncated to 200 chars for safety) and execute it
            log.info(f"Query: {query[:200]}{'...' if len(query) > 200 else ''}")
            results = db_context.execute_query(query)

        # Log the number of rows returned and serialize results to JSON
        log.info(f"Query returned {len(results)} rows")
        return log.collect(json.dumps(results, default=str))

    except Exception as e:
        # Catch any unexpected errors and return a user-friendly error message
        log.error(f"Query execution error on {dbname}: {e}")
        return f"Query Execution Error: {e}"


def tool_get_table_data(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    table_name: str,
    limit: int = 100,
    port: int = 0
) -> str:
    """
    MCP tool for fetching the first N rows from a database table.

    This tool safely retrieves a limited set of rows from a specified table
    using parameterized LIMIT syntax, with table name validation to prevent
    SQL injection.

    Args:
        db_type: Type of database to connect to (postgres, mariadb, mysql, mssql).
        host: Database server hostname or IP address.
        user: Database username for authentication.
        password: Database password for authentication.
        dbname: Name of the database containing the table.
        table_name: Name of the table to query (must be a valid SQL identifier).
        limit: Maximum number of rows to return (default: 100).
        port: Database port number (0 = use default for db_type).

    Returns:
        A JSON string containing the table rows as a list of dictionaries,
        or an error message string if the operation fails.
        1. Validates the table name against SQL identifier patterns.
        2. Resolves the default port if not explicitly provided.
        3. Creates a ConnectionDetails object and gets the appropriate strategy.
        4. Constructs a SELECT query with LIMIT (MSSQL uses TOP syntax).
        5. Executes the query via the database context manager.
        6. Returns the results as a JSON string.
    """
    # Initialize the log collector for tracking tool operations
    log = LogCollector(f"{__name__}.get_table_data")

    # Resolve the default port if not explicitly provided (port=0 means use default)
    if not port:
        port = _default_port(db_type)

    try:
        # Validate the table name to prevent SQL injection
        _validate_identifier(table_name)

        # Log the table data fetch request
        log.info(f"Fetching {limit} rows from {db_type}://{host}:{port}/{dbname}.{table_name}")

        # Create a ConnectionDetails Pydantic model to hold connection parameters
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )

        # Get the appropriate database strategy based on db_type and connection details
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        # Construct the SELECT query with LIMIT: MSSQL uses TOP syntax, others use LIMIT
        if db_type == "mssql":
            query = f"SELECT TOP {limit} * FROM {table_name}"
        else:
            query = f"SELECT * FROM {table_name} LIMIT {limit}"

        # Open a database context manager: connects, executes query, then disconnects
        with strategy as db_context:
            results = db_context.execute_query(query)

        # Log the number of rows retrieved and return as JSON
        log.info(f"Retrieved {len(results)} rows from {table_name}")
        return json.dumps(results, default=str)

    except Exception as e:
        # Catch any unexpected errors and return a user-friendly error message
        log.error(f"Data retrieval error for {table_name}: {e}")
        return f"Data Retrieval Error: {e}"


def register_data_tools(mcp, db_manager=None):
    """
    Register data-related MCP tools with the FastMCP server.
        Maps the tool_run_sql and tool_get_table_data functions to their
        respective MCP tool names for invocation by MCP clients.

    Args:
        mcp: The FastMCP server instance to register tools on.
        db_manager: Optional DbManager instance (not used by data tools directly).
    """
    # Register the raw SQL query execution tool
    mcp.tool(name="run_read_only_sql")(tool_run_sql)
    # Register the table data fetch tool
    mcp.tool(name="get_table_data")(tool_get_table_data)
