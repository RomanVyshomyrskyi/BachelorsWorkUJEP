"""
MSSQL Strategy - Database operations for Microsoft SQL Server.

Implements the DatabaseStrategy interface for Microsoft SQL Server databases
using the pyodbc driver with ODBC Driver 17. Provides connection management
with MARS disabled, schema extraction from INFORMATION_SCHEMA, and read-only
query execution with row limiting.
"""

import logging
import pyodbc
from .base import DatabaseStrategy, MAX_ROWS
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)


class MSSQLStrategy(DatabaseStrategy):
    """
    Database strategy implementation for Microsoft SQL Server using pyodbc.

    This strategy provides MSSQL-specific connection management using ODBC,
    schema extraction from INFORMATION_SCHEMA views, and read-only query
    execution with MARS disabled for safety.

    Connection Security:
        - Sets MARS_Connection=no to disable Multiple Active Result Sets,
          preventing concurrent query execution on the same connection.
        - Executes SET LOCK_TIMEOUT 5000 to limit lock wait time to 5 seconds.
        - Executes SET QUERY_GOVERNOR_COST_LIMIT 0 to disable query cost limiting.
        - Validates multi-statement queries by rejecting semicolons in the query.

    Schema Extraction:
        - Queries INFORMATION_SCHEMA.TABLES and INFORMATION_SCHEMA.COLUMNS
          for table and column metadata, filtered by database catalog.
        - Queries INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS with joins to
          TABLE_CONSTRAINTS and KEY_COLUMN_USAGE for foreign key relationships.

    Query Execution:
        - Enforces read-only validation via inherited _validate_read_only_query.
        - Additional MSSQL-specific check: rejects queries containing semicolons
          to prevent multi-statement execution at the application level.
        - Fetches results in batches of 500 rows using fetchmany().
        - Limits results to MAX_ROWS (1000) to prevent memory exhaustion.

    Usage:
        >>> details = {"host": "localhost\\SQLEXPRESS", "user": "sa", "password": "secret",
        ...            "dbname": "mydb", "port": 1433}
        >>> strategy = MSSQLStrategy(details)
        >>> with strategy as db:
        ...     schema = db.get_schema_representation()
        ...     results = db.execute_query("SELECT TOP 10 * FROM users")
    """

    def connect(self):
        """Establish a connection to the MSSQL database using pyodbc.

        Creates a pyodbc connection using ODBC Driver 17 for SQL Server with
        MARS disabled and lock timeout configured to 5 seconds. Stores the
        connection object for subsequent operations.

        Raises:
            ConnectionError: If the connection fails (invalid credentials,
                unreachable server, driver not installed, etc.).
        """
        # Extract connection parameters from the stored details dictionary
        db = self.connection_details

        # Log the connection attempt with server and database information
        logger.info(f"Connecting to MSSQL at {db['host']}/{db['dbname']}")

        try:
            # Build the ODBC connection string with required parameters
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}};"
                f"SERVER={db['host']};"
                f"DATABASE={db['dbname']};"
                f"UID={db['user']};"
                f"PWD={db['password']};"
                # Disable multiple active result sets and multi-statement for safety
                f"MARS_Connection=no;"
            )

            # Establish the pyodbc connection using the constructed connection string
            self.connection = pyodbc.connect(conn_str)

            # Set lock timeout to 5000ms (5 seconds) to prevent indefinite lock waits
            self.connection.execute("SET LOCK_TIMEOUT 5000")

            # Disable query governor cost limit (0 = unlimited, but set explicitly for clarity)
            self.connection.execute("SET QUERY_GOVERNOR_COST_LIMIT 0")

            # Log successful connection for audit/debugging purposes
            logger.info(f"Connected to MSSQL: {db['dbname']}")
        except Exception as e:
            # Log the full error for debugging and raise a user-friendly ConnectionError
            logger.error(f"MSSQL connection failed: {e}")
            raise ConnectionError("Failed to connect to database. Please verify your credentials and network.")

    def disconnect(self):
        """Close the MSSQL database connection and release resources.

        Closes the underlying pyodbc connection and sets the internal
        reference to ``None`` to prevent use-after-close errors.
        """
        # Only attempt to close if a connection object exists
        if self.connection:
            self.connection.close()
            logger.info("MSSQL connection closed")
        # Clear the connection reference to prevent use-after-close
        self.connection = None

    def get_schema_representation(self) -> str:
        """
        Extract the MSSQL database schema as a formatted string.

        Queries INFORMATION_SCHEMA to retrieve table definitions, column
        metadata (names, types, nullability), and foreign key relationships,
        filtered by the target database catalog.

        Returns:
            A formatted string with table listings, column details, and
            foreign key relationships.

        Raises:
            ConnectionError: If not currently connected to the database.
        """
        # Verify that a connection is established before attempting schema extraction
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        # Log the schema extraction operation
        logger.info(f"Extracting schema for {self.connection_details['dbname']}")

        # Open a cursor and execute schema extraction queries
        with self.connection.cursor() as cursor:
            # Query 1: Extract table names, column names, data types, and nullability
            # Filters by the specific database catalog using parameterized query (?)
            cursor.execute("""
                SELECT
                    t.TABLE_NAME,
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.IS_NULLABLE
                FROM
                    INFORMATION_SCHEMA.TABLES t
                JOIN
                    INFORMATION_SCHEMA.COLUMNS c ON t.TABLE_NAME = c.TABLE_NAME
                WHERE
                    t.TABLE_TYPE = 'BASE TABLE' AND t.TABLE_CATALOG = ?
                ORDER BY
                    t.TABLE_NAME, c.ORDINAL_POSITION;
            """, (self.connection_details['dbname'],))
            tables_and_columns = cursor.fetchall()

            # Query 2: Extract foreign key relationships
            # Joins REFERENTIAL_CONSTRAINTS, TABLE_CONSTRAINTS (for FK and PK),
            # and KEY_COLUMN_USAGE (for column mapping) to build complete FK paths
            cursor.execute("""
                SELECT
                    fk.TABLE_NAME AS foreign_table,
                    fk_cols.COLUMN_NAME AS foreign_column,
                    pk.TABLE_NAME AS primary_table,
                    pk_cols.COLUMN_NAME AS primary_column
                FROM
                    INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS fk
                    ON rc.CONSTRAINT_CATALOG = fk.CONSTRAINT_CATALOG
                    AND rc.CONSTRAINT_SCHEMA = fk.CONSTRAINT_SCHEMA
                    AND rc.CONSTRAINT_NAME = fk.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.TABLE_CONSTRAINTS pk
                    ON rc.UNIQUE_CONSTRAINT_CATALOG = pk.CONSTRAINT_CATALOG
                    AND rc.UNIQUE_CONSTRAINT_SCHEMA = pk.CONSTRAINT_SCHEMA
                    AND rc.UNIQUE_CONSTRAINT_NAME = pk.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE fk_cols
                    ON rc.CONSTRAINT_CATALOG = fk_cols.CONSTRAINT_CATALOG
                    AND rc.CONSTRAINT_SCHEMA = fk_cols.CONSTRAINT_SCHEMA
                    AND rc.CONSTRAINT_NAME = fk_cols.CONSTRAINT_NAME
                JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE pk_cols
                    ON rc.UNIQUE_CONSTRAINT_CATALOG = pk_cols.CONSTRAINT_CATALOG
                    AND rc.UNIQUE_CONSTRAINT_SCHEMA = pk_cols.CONSTRAINT_SCHEMA
                    AND rc.UNIQUE_CONSTRAINT_NAME = pk_cols.CONSTRAINT_NAME
                    AND fk_cols.ORDINAL_POSITION = pk_cols.ORDINAL_POSITION
                WHERE fk.TABLE_CATALOG = ?
            """, (self.connection_details['dbname'],))
            relationships = cursor.fetchall()

        # Format the extracted schema data into a human-readable string
        return format_schema(self.connection_details['dbname'], "MSSQL", tables_and_columns, relationships)

    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        """Execute a read-only MSSQL query with row limiting.

        Executes a read-only SQL query on the MSSQL database with an
        additional multi-statement check that rejects queries containing
        semicolons. Results are fetched in batches of 500 rows and returned
        as a list of dictionaries.

        Args:
            query: The SQL SELECT query to execute (validated as read-only).
            max_rows: Maximum number of rows to return (default: 1000).

        Returns:
            A list of dictionaries, each representing a row with column
            names as keys.

        Raises:
            ConnectionError: If not currently connected to the database.
            ValueError: If the query contains semicolons (multi-statement).
            RuntimeError: If a pyodbc error occurs during execution.
        """
        # Verify that a connection is established before attempting query execution
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        # Validate the query as read-only (inherited security check)
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

        # Additional MSSQL-specific multi-statement check: reject semicolons
        # This is an extra layer of defense since MSSQL supports batched statements
        if ';' in cleaned:
            raise ValueError("Security violation: Multi-statement queries are not allowed on MSSQL")

        try:
            # Open a cursor and execute the validated query
            with self.connection.cursor() as cursor:
                cursor.execute(cleaned)

                # Check if the query returned columns (i.e., it's a SELECT that produced rows)
                if cursor.description:
                    # Extract column names from the cursor description metadata
                    columns = [desc[0] for desc in cursor.description]

                    # Fetch results in batches for memory efficiency
                    results = []
                    # Use fetchmany for efficient pagination with row limit
                    while True:
                        # Fetch up to 500 rows at a time
                        batch = cursor.fetchmany(500)
                        if not batch:
                            break

                        # Convert each row tuple to a dictionary with column names as keys
                        for row in batch:
                            results.append(dict(zip(columns, row)))
                            # Stop if we've reached the maximum row limit
                            if len(results) >= max_rows:
                                break

                        # Stop the outer loop if we've reached the maximum row limit
                        if len(results) >= max_rows:
                            break

                    # Log the number of rows returned
                    logger.info(f"Query returned {len(results)} rows")
                    return results

                # Query executed but returned no columns
                logger.warning("Query returned no results")
                return []

        except pyodbc.Error as e:
            # Log the driver-level error details and raise a sanitized RuntimeError
            logger.error(f"Database error: {e}")
            # Do not expose driver-level error details to the caller for security
            raise RuntimeError("A database error occurred while executing the query.")

    def execute_ddl(self, query: str) -> dict:
        """
        Execute a non-SELECT statement (CREATE, INSERT, UPDATE, etc.).

        Executes a DDL or DML statement that does not return rows.
        Automatically commits the transaction upon success.

        Args:
            query: The SQL statement to execute (validated before calling).

        Returns:
            Dictionary with:
            - success: True
            - message: Human-readable description of the result
            - affected_rows: Number of rows affected (0 for DDL)

        Raises:
            ConnectionError: If not currently connected to the database.
            ValueError: If the query contains semicolons (multi-statement).
            RuntimeError: If a pyodbc error occurs during execution.
        """
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        cleaned = self._validate_dml_query(
            query,
            allowed_ops=frozenset(['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'REPLACE']),
            always_forbidden=frozenset([])
        )

        if ';' in cleaned:
            raise ValueError("Security violation: Multi-statement queries are not allowed on MSSQL")

        logger.info(f"Executing DDL/DML ({len(cleaned)} chars)")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(cleaned)
                self.connection.commit()

                affected = cursor.rowcount
                message = f"{affected} row(s) affected" if affected > 0 else "Statement executed successfully"

                logger.info(f"DDL/DML executed: {message}")
                return {
                    "success": True,
                    "message": message,
                    "affected_rows": affected,
                }

        except pyodbc.Error as e:
            logger.error(f"Database error: {e}")
            raise RuntimeError(f"Database error: {e}")

    def get_tables_list(self, schema: str = None) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.TABLE_NAME,
                    t.TABLE_SCHEMA,
                    p.rows AS table_rows,
                    c.column_count
                FROM INFORMATION_SCHEMA.TABLES t
                JOIN (
                    SELECT TABLE_SCHEMA, TABLE_NAME, COUNT(*) AS column_count
                    FROM INFORMATION_SCHEMA.COLUMNS
                    GROUP BY TABLE_SCHEMA, TABLE_NAME
                ) c ON t.TABLE_NAME = c.TABLE_NAME AND t.TABLE_SCHEMA = c.TABLE_SCHEMA
                JOIN sys.sysindexes p ON t.TABLE_NAME = OBJECT_NAME(p.id) AND p.indid IN (0, 1)
                WHERE t.TABLE_TYPE = 'BASE TABLE'
                ORDER BY t.TABLE_NAME;
            """)
            rows = cursor.fetchall()
        return [
            {"name": r[0], "schema": r[1], "table_rows": int(r[2]) if r[2] else 0, "column_count": r[3]}
            for r in rows
        ]

    def get_table_columns(self, table_name: str, schema: str = None) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.COLUMN_NAME,
                    c.DATA_TYPE,
                    c.IS_NULLABLE,
                    CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
                    CAST(c.CHARACTER_MAXIMUM_LENGTH AS INT) AS max_length
                FROM INFORMATION_SCHEMA.COLUMNS c
                LEFT JOIN (
                    SELECT KU.TABLE_SCHEMA, KU.TABLE_NAME, KU.COLUMN_NAME
                    FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
                    JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE KU
                        ON tc.CONSTRAINT_NAME = KU.CONSTRAINT_NAME
                        AND tc.CONSTRAINT_SCHEMA = KU.CONSTRAINT_SCHEMA
                    WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
                ) pk ON c.TABLE_NAME = pk.TABLE_NAME AND c.COLUMN_NAME = pk.COLUMN_NAME AND c.TABLE_SCHEMA = pk.TABLE_SCHEMA
                WHERE c.TABLE_NAME = ?
                ORDER BY c.ORDINAL_POSITION;
            """, (table_name,))
            rows = cursor.fetchall()
        return [
            {
                "name": r[0],
                "type": r[1],
                "nullable": r[2] == 'YES',
                "is_primary_key": bool(r[3]),
                "max_length": int(r[4]) if r[4] else None,
            }
            for r in rows
        ]

    def batch_insert(self, table_name: str, columns: list[str], rows: list[list], schema: str = None) -> int:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        col_names = ", ".join(f"[{c}]" for c in columns)
        placeholders = ", ".join(["?"] * len(columns))
        sql = f"INSERT INTO [{table_name}] ({col_names}) VALUES ({placeholders})"
        logger.info(f"Executing batch insert into {table_name}: {len(rows)} rows")
        with self.connection.cursor() as cursor:
            processed = []
            for row in rows:
                processed.append(tuple(None if (v is None or v == '') else v for v in row))
            cursor.executemany(sql, processed)
            self.connection.commit()
            logger.info(f"Batch insert completed: {cursor.rowcount} rows inserted")
            return cursor.rowcount
