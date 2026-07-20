import sqlparse
from sqlparse.sql import Statement
import logging
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)

# Maximum number of rows any query can return
MAX_ROWS = 1000

# Maximum query execution time in seconds
QUERY_TIMEOUT_SECONDS = 30

# Keywords that indicate write/dangerous operations
FORBIDDEN_KEYWORDS = frozenset([
    'INSERT', 'UPDATE', 'DELETE', 'REPLACE', 'MERGE',
    'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'RENAME',
    'GRANT', 'REVOKE', 'COMMIT', 'ROLLBACK',
    'EXEC', 'EXECUTE', 'xp_', 'sp_',
    'LOAD', 'INTO OUTFILE', 'INTO DUMPFILE',
    'BULK', 'OPENQUERY', 'OPENDATASOURCE',
])


class DatabaseStrategy(ABC):
    """
    Abstract base class for a database analysis strategy.
    This defines the common interface for all database-specific implementations.
    """
    def __init__(self, connection_details: dict):
        """
        Initializes the strategy with the necessary connection details.
        
        :param connection_details: A dictionary containing user, password, host, port, and dbname.
        """
        self.connection_details = connection_details
        self.connection = None

    @abstractmethod
    def connect(self):
        """
        Establishes a connection to the database.
        Should raise an exception if the connection fails.
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Closes the database connection.
        """
        pass

    @abstractmethod
    def get_schema_representation(self) -> str:
        """
        Retrieves the database schema and returns it as a single,
        descriptive string. This string will be used as context for the LLM.
        
        The representation should include:
        - Table names
        - Column names, data types, and nullability for each table
        - Primary key constraints
        - Foreign key relationships
        
        :return: A string detailing the database schema.
        """
        pass

    @staticmethod
    def _validate_read_only_query(query: str) -> str:
        """
        Validates that a SQL query is read-only using sqlparse AST parsing.
        
        This prevents:
        - Write operations (INSERT, UPDATE, DELETE, etc.)
        - DDL operations (CREATE, ALTER, DROP, etc.)
        - Multi-statement execution
        - Dangerous stored procedures (xp_, sp_)
        
        :param query: Raw SQL query string
        :return: The validated query string (same as input if valid)
        :raises ValueError: If the query is not read-only or contains dangerous patterns
        """
        if not query or not query.strip():
            raise ValueError("Security violation: Empty query")

        # Strip comments (line comments and block comments)
        cleaned = sqlparse.format(query, strip_comments=True)
        cleaned = cleaned.strip()

        if not cleaned:
            raise ValueError("Security violation: Query became empty after stripping comments")

        # Parse the SQL
        parsed = sqlparse.parse(cleaned)
        if not parsed:
            raise ValueError("Security violation: Unable to parse query")

        # sqlparse can split into multiple statements; we only allow exactly one
        statements = [s for s in parsed if s.ttype is not None or str(s).strip()]
        if len(statements) > 1:
            raise ValueError("Security violation: Multi-statement queries are not allowed")

        stmt: Statement = statements[0]
        stmt_text = str(stmt).strip()
        stmt_upper = stmt_text.upper()

        # Check for dangerous keywords anywhere in the query
        for keyword in FORBIDDEN_KEYWORDS:
            if keyword in stmt_upper:
                raise ValueError(
                    f"Security violation: Query contains forbidden keyword '{keyword}'"
                )

        # Check that the statement type is SELECT (or WITH for CTEs)
        ttype = stmt.get_type()
        if ttype not in ('SELECT', 'WITH'):
            # sqlparse may return None or other types for non-standard queries
            # Fall back to checking the first token
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

        # Additional check: reject queries that look like they might use
        # dangerous system procedures or extended commands
        if 'xp_' in stmt_upper or 'sp_executesql' in stmt_upper:
            raise ValueError("Security violation: System procedure calls are not allowed")

        logger.info(f"Query validation passed (SELECT-only, {len(cleaned)} chars)")
        return cleaned

    @staticmethod
    def _enforce_row_limit(rows: list[dict], max_rows: int = MAX_ROWS) -> list[dict]:
        """Truncate result set to the maximum allowed rows."""
        if len(rows) > max_rows:
            logger.warning(
                f"Result set truncated from {len(rows)} to {max_rows} rows"
            )
            return rows[:max_rows]
        return rows

    @abstractmethod
    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        """
        Executes a raw SQL query (validated as read-only) and returns results.
        
        :param query: The SQL SELECT query to execute.
        :param max_rows: Maximum number of rows to return (default: 1000).
        :return: A list of dictionaries, where each dictionary represents a row.
        """
        pass

    def __enter__(self):
        """Allows the strategy to be used as a context manager."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Ensures disconnection when the context is exited."""
        self.disconnect()
