"""
Base Database Strategy - Abstract base class for database operations.

Defines the common interface for all database-specific strategy implementations.
Includes read-only query validation, row limiting, and context manager support
for safe, resource-managed database access across PostgreSQL, MariaDB/MySQL,
and Microsoft SQL Server.
"""

import sqlparse
from sqlparse.sql import Statement
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Maximum number of rows any query can return to prevent memory exhaustion
MAX_ROWS = 1000

# Maximum query execution time in seconds before timeout is triggered
QUERY_TIMEOUT_SECONDS = 30

# Keywords that indicate write/dangerous operations - used for read-only enforcement
FORBIDDEN_KEYWORDS = frozenset([
    # Data modification operations
    'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'MERGE',
    # Data definition operations
    'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME',
    # Security operations
    'GRANT', 'REVOKE',
    # Transaction control
    'COMMIT', 'ROLLBACK',
    # Stored procedure execution
    'EXEC', 'EXECUTE', 'xp_', 'sp_',
    # Bulk operations and remote queries
    'LOAD', 'INTO OUTFILE', 'INTO DUMPFILE',
    'BULK', 'OPENQUERY', 'OPENDATASOURCE',
])


class DatabaseStrategy(ABC):
    """
    Abstract base class defining the common interface for database operations.

    This class establishes the strategy pattern contract for all database-specific
    implementations (PostgresStrategy, MariaDBStrategy, MSSQLStrategy). It provides:
    - Connection management via context manager protocol (__enter__/__exit__)
    - Read-only query enforcement using sqlparse AST analysis
    - Result set row limiting to prevent memory exhaustion
    - Abstract methods for connect, disconnect, execute_query, and get_schema_representation
        The strategy pattern allows the system to work with multiple database
        types through a unified interface. Each concrete strategy handles the
        database-specific driver details (psycopg2, mysql-connector, pyodbc)
        while inheriting shared security and resource management from this base.

    Read-Only Query Enforcement:
        The _validate_read_only_query method uses sqlparse to parse SQL queries
        and ensure they are read-only. It checks for:
        1. Empty queries or queries that become empty after comment stripping.
        2. Multi-statement queries (only one statement allowed).
        3. Forbidden keywords (INSERT, UPDATE, DROP, EXEC, etc.).
        4. Non-SELECT statement types (verifies first token is SELECT or WITH).
        5. System procedure calls (xp_, sp_executesql).

    Row Limiting:
        All queries are automatically limited to MAX_ROWS (1000) to prevent
        memory exhaustion from large result sets. The _enforce_row_limit
        method truncates results if they exceed this threshold.

    Usage:
        Strategies are used as context managers for automatic connection
        and disconnection:

        >>> strategy = PostgresStrategy(connection_details)
        >>> with strategy as db:
        ...     results = db.execute_query("SELECT * FROM users")
        >>> # Connection is automatically closed after the with block

        Examples:
            >>> strategy = get_db_strategy("postgres", {
            ...     "host": "localhost", "user": "admin", "password": "secret",
            ...     "dbname": "analytics", "port": 5432})
            >>> with strategy as db:
            ...     rows = db.execute_query("SELECT id, name FROM users LIMIT 5")
            ...     for row in rows:
            ...         print(row["name"])
            ...     schema = db.get_schema_representation()
            >>> # Connection closed automatically

            >>> # Read-only enforcement example:
            >>> DatabaseStrategy._validate_read_only_query("SELECT * FROM users")
            'SELECT * FROM users'
            >>> try:
            ...     DatabaseStrategy._validate_read_only_query("DROP TABLE users")
            ... except ValueError as e:
            ...     print(e)
            Security violation: Query contains forbidden keyword 'DROP'
    """

    def __init__(self, connection_details: dict):
        """
        Initialize the strategy with database connection parameters.

        Args:
            connection_details: A dictionary containing connection parameters
                with keys: host, user, password, dbname, and optionally port.
            Stores the connection details and initializes the connection
            attribute to None. The actual connection is not established
            until connect() is called.
        """
        # Store the connection parameters for use in connect() method
        self.connection_details = connection_details
        # Connection object (driver-specific) - initialized as None
        self.connection = None

    @abstractmethod
    def connect(self):
        """
        Establish a connection to the database using stored connection details.

        This method must be implemented by each concrete strategy to handle
        database-specific connection logic, including driver initialization,
        credential validation, and connection state management.
            Concrete implementations should:
            1. Extract connection parameters from self.connection_details.
            2. Create a driver-specific connection object.
            3. Set any connection-level security options (timeouts, etc.).
            4. Store the connection in self.connection.
            5. Raise ConnectionError with a user-friendly message on failure.

        Raises:
            ConnectionError: If the database connection cannot be established.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Close the database connection and release resources.

        This method must be implemented by each concrete strategy to handle
        database-specific connection cleanup.
            Concrete implementations should:
            1. Check if a connection exists.
            2. Close the connection if open.
            3. Set self.connection to None to prevent use-after-close.

        Note:
            This is called automatically when exiting a context manager block.
        """
        pass

    @abstractmethod
    def get_schema_representation(self) -> str:
        """
        Extract and format the database schema as a human-readable string.

        This method queries the database's information schema to retrieve
        table definitions, column metadata, and foreign key relationships,
        then formats them into a structured string representation.

        Returns:
            A formatted string containing:
            - Database name and type header.
            - For each table: table name, columns with data types and nullability.
            - Foreign key relationships showing table-to-table references.

        Raises:
            ConnectionError: If not currently connected to the database.
        """
        pass

    @staticmethod
    def _validate_read_only_query(query: str) -> str:
        """
        Validate that a SQL query is read-only using sqlparse AST parsing.

        This is the core security mechanism that prevents data modification,
        schema changes, and other dangerous operations. It performs multi-layer
        analysis of the query:

        Layer 1 - Content Safety:
            - Rejects empty queries and queries that become empty after
              comment stripping (which could hide malicious content).
            - Rejects multi-statement queries (only single SELECT allowed).

        Layer 2 - Keyword Filtering:
            - Scans the query for forbidden keywords (INSERT, UPDATE, DROP,
              EXEC, xp_, sp_executesql, etc.) anywhere in the text.
            - Uses uppercase comparison for case-insensitive matching.

        Layer 3 - Statement Type Verification:
            - Uses sqlparse to determine the actual statement type.
            - Only allows SELECT and WITH (CTE) statements.
            - Falls back to first-token analysis for edge cases.

        Args:
            query: Raw SQL query string to validate.

        Returns:
            The cleaned query string (comments stripped, whitespace normalized)
            if the query passes all validation checks.

        Raises:
            ValueError: If the query violates any security rule, with a
                        descriptive message explaining which rule was violated.

        Examples:
            >>> DatabaseStrategy._validate_read_only_query("SELECT * FROM users")
            'SELECT * FROM users'
            >>> DatabaseStrategy._validate_read_only_query("DROP TABLE users")
            ValueError: Security violation: Query contains forbidden keyword 'DROP'
        """
        # Reject empty or whitespace-only queries immediately
        if not query or not query.strip():
            raise ValueError("Security violation: Empty query")

        # Strip SQL comments (-- and /* */ blocks) to prevent hiding malicious content
        cleaned = sqlparse.format(query, strip_comments=True)
        cleaned = cleaned.strip()

        # Ensure the query didn't become empty after comment removal
        if not cleaned:
            raise ValueError("Security violation: Query became empty after stripping comments")

        # Parse the cleaned SQL into an AST (Abstract Syntax Tree)
        parsed = sqlparse.parse(cleaned)
        if not parsed:
            raise ValueError("Security violation: Unable to parse query")

        # sqlparse can split input into multiple statements; we only allow exactly one
        statements = [s for s in parsed if s.ttype is not None or str(s).strip()]
        if len(statements) > 1:
            raise ValueError("Security violation: Multi-statement queries are not allowed")

        # Extract the single allowed statement from the parsed result
        stmt: Statement = statements[0]
        stmt_text = str(stmt).strip()
        stmt_upper = stmt_text.upper()

        # Scan for any forbidden keywords anywhere in the query text (case-insensitive)
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in stmt_upper:
                raise ValueError(
                    f"Security violation: Query contains forbidden keyword '{keyword}'"
                )

        # Use sqlparse to determine the statement type (SELECT, WITH, etc.)
        ttype = stmt.get_type()
        if ttype not in ('SELECT', 'WITH'):
            # If sqlparse can't determine the type, fall back to checking the first token
            first_token = stmt.token_first(skip_ws=True, skip_com=True)
            if first_token:
                first_val = str(first_token).upper()
                if first_val not in ('SELECT', 'WITH'):
                    raise ValueError(
                        f"Security violation: Only SELECT/WITH queries are allowed. "
                        f"Detected statement type: '{first_val}'"
                    )
            else:
                raise ValueError("Security violation: Unable to determine query type")

        # Additional MSSQL-specific check: reject system procedure calls
        if 'xp_' in stmt_upper or 'sp_executesql' in stmt_upper:
            raise ValueError("Security violation: System procedure calls are not allowed")

        # Log successful validation and return the cleaned query
        logger.info(f"Query validation passed (SELECT-only, {len(cleaned)} chars)")
        return cleaned

    @staticmethod
    def _enforce_row_limit(rows: list[dict], max_rows: int = MAX_ROWS) -> list[dict]:
        """
        Truncate a result set to the maximum allowed number of rows.

        This is a safety mechanism to prevent memory exhaustion from queries
        that return extremely large result sets.

        Args:
            rows: The list of row dictionaries to potentially truncate.
            max_rows: Maximum number of rows to keep (default: MAX_ROWS = 1000).

        Returns:
            The rows list, truncated to max_rows if it exceeds the limit,
            or the original list if it is within the limit.
            1. Checks if the result set exceeds the row limit.
            2. Logs a warning if truncation occurs.
            3. Returns only the first max_rows entries if truncated.
        """
        # Check if the result set exceeds the maximum allowed rows
        if len(rows) > max_rows:
            # Log a warning and truncate the result set
            logger.warning(
                f"Result set truncated from {len(rows)} to {max_rows} rows"
            )
            return rows[:max_rows]
        return rows

    @abstractmethod
    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        """
        Execute a validated read-only SQL query and return results.

        This method must be implemented by each concrete strategy to handle
        database-specific query execution, including driver-specific connection
        handling, result fetching, and error handling.

        Args:
            query: The SQL SELECT query to execute (must pass _validate_read_only_query).
            max_rows: Maximum number of rows to return (default: MAX_ROWS = 1000).

        Returns:
            A list of dictionaries, where each dictionary represents a row
            with column names as keys and row values as dictionary values.

        Raises:
            ConnectionError: If not currently connected to the database.
            TimeoutError: If the query execution exceeds the timeout limit.
            RuntimeError: If a database error occurs during execution.

        Note:
            The query is automatically validated as read-only before execution.
        """
        pass

    def __enter__(self):
        """
        Enter the context manager: establish the database connection.

        This method is called automatically when entering a 'with' block
        using this strategy as a context manager.

        Returns:
            self: The strategy instance, ready for query execution.

        Examples:
            >>> with PostgresStrategy(details) as db:
            ...     results = db.execute_query("SELECT 1")
        """
        # Establish the database connection before entering the with block body
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit the context manager: ensure the database connection is closed.

        This method is called automatically when exiting a 'with' block,
        regardless of whether an exception occurred. It ensures connection
        cleanup even in error scenarios.

        Args:
            exc_type: The exception type if an exception was raised, or None.
            exc_val: The exception value if an exception was raised, or None.
            exc_tb: The exception traceback if an exception was raised, or None.
            Always attempts to close the connection, even if an exception
            occurred during the with block, to prevent resource leaks.
        """
        # Ensure the database connection is closed when exiting the context
        self.disconnect()
