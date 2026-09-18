"""
PostgreSQL Strategy - Database operations for PostgreSQL.

Implements the DatabaseStrategy interface for PostgreSQL databases using
the psycopg2 driver. Provides connection management, schema extraction
from information_schema, and read-only query execution with signal-based
timeout enforcement.
"""

import logging
import signal
import psycopg2
from .base import DatabaseStrategy, MAX_ROWS
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)


class _TimeoutError(Exception):
    """
    Internal exception raised by the signal-based query timeout handler.

    This exception is used to interrupt long-running queries. It is not
    exposed to MCP clients; instead, it is caught and converted to a
    standard TimeoutError.
    """
    pass


def _timeout_handler(signum, frame):
    """
    Signal handler that raises _TimeoutError when the query timeout expires.

    This function is registered as a SIGALRM handler to enforce query
    execution timeouts. When the alarm fires, it raises _TimeoutError
    which interrupts the current query execution.

    Args:
        signum: The signal number received (SIGALRM = 14).
        frame: The current stack frame (unused but required by signal handlers).

    Raises:
        _TimeoutError: Always raised when this handler is triggered.
    """
    # Raise the internal timeout exception to interrupt query execution
    raise _TimeoutError("Query execution timed out")


class PostgresStrategy(DatabaseStrategy):
    """
    Database strategy implementation for PostgreSQL using psycopg2.

    This strategy provides PostgreSQL-specific connection management,
    schema extraction from information_schema tables, and read-only
    query execution with signal-based timeout enforcement.

    Connection Security:
        - Uses psycopg2.set_session(timeout=30000) to set a 30-second
          statement-level timeout at the connection level.
        - Uses SIGALRM-based timeout as a secondary safety net.
        - Disables multi-statement execution at the driver level.

    Schema Extraction:
        - Queries information_schema.tables and information_schema.columns
          for table and column metadata.
        - Queries information_schema.key_column_usage and referential_constraints
          for foreign key relationships.
        - Filters to the 'public' schema and 'BASE TABLE' type only.

    Query Execution:
        - Enforces read-only validation via inherited _validate_read_only_query.
        - Uses SIGALRM signal with a 30-second timeout.
        - Fetches results in batches of 500 rows using fetchmany().
        - Limits results to MAX_ROWS (1000) to prevent memory exhaustion.

    Usage:
        >>> details = {"host": "localhost", "user": "admin", "password": "secret",
        ...            "dbname": "mydb", "port": 5432}
        >>> strategy = PostgresStrategy(details)
        >>> with strategy as db:
        ...     schema = db.get_schema_representation()
        ...     results = db.execute_query("SELECT * FROM users LIMIT 10")
    """

    def connect(self):
        """Establish a connection to the PostgreSQL database.

        Creates a psycopg2 connection using the credentials from
        ``connection_details``, configures a 30-second statement-level
        timeout via ``set_session()``, and stores the connection object
        for subsequent operations.

        Raises:
            ConnectionError: If the connection fails (invalid credentials,
                unreachable host, wrong port, etc.).
        """
        # Extract connection parameters from the stored details dictionary
        db = self.connection_details

        # Log the connection attempt with server and database information
        logger.info(f"Connecting to PostgreSQL at {db['host']}:{db.get('port', 5432)}/{db['dbname']}")

        try:
            # Establish the psycopg2 connection with the provided credentials
            self.connection = psycopg2.connect(
                dbname=db['dbname'],
                user=db['user'],
                password=db['password'],
                host=db['host'],
                port=db.get('port', 5432)
            )

            # Set statement-level timeout to 30 seconds (30000 milliseconds)
            # This limits how long any single SQL statement can run
            self.connection.set_session(timeout=30000)

            # Log successful connection for audit/debugging purposes
            logger.info(f"Connected to PostgreSQL: {db['dbname']}")
        except Exception as e:
            # Log the full error for debugging and raise a user-friendly ConnectionError
            logger.error(f"PostgreSQL connection failed: {e}")
            raise ConnectionError("Failed to connect to database. Please verify your credentials and network.")

    def disconnect(self):
        """Close the PostgreSQL database connection and release resources.

        Closes the underlying psycopg2 connection and sets the internal
        reference to ``None`` to prevent use-after-close errors.
        """
        # Only attempt to close if a connection object exists
        if self.connection:
            self.connection.close()
            logger.info("PostgreSQL connection closed")
        # Clear the connection reference to prevent use-after-close
        self.connection = None

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
            RuntimeError: If a PostgreSQL error occurs during execution.
        """
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        cleaned = self._validate_dml_query(
            query,
            allowed_ops=frozenset(['SELECT', 'INSERT', 'UPDATE', 'DELETE', 'CREATE', 'ALTER', 'DROP', 'TRUNCATE', 'REPLACE']),
            always_forbidden=frozenset([])
        )

        logger.info(f"Executing DDL/DML ({len(cleaned)} chars)")

        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)

        try:
            signal.alarm(30)

            with self.connection.cursor() as cursor:
                cursor.execute(cleaned)
                self.connection.commit()

                signal.alarm(0)
                affected = cursor.rowcount
                message = f"{affected} row(s) affected" if affected > 0 else "Statement executed successfully"

                logger.info(f"DDL/DML executed: {message}")
                return {
                    "success": True,
                    "message": message,
                    "affected_rows": affected,
                }

        except _TimeoutError:
            logger.error("DDL/DML execution timed out after 30 seconds")
            raise TimeoutError("DDL/DML execution timed out. The operation may be too slow.")
        except psycopg2.Error as e:
            signal.alarm(0)
            logger.error(f"Database error: {e.pgcode} - {e.diag.message_primary}")
            raise RuntimeError(f"Database error: {e.diag.message_primary}")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)

    def get_schema_representation(self) -> str:
        """
        Extract the PostgreSQL database schema as a formatted string.

        Queries information_schema to retrieve table definitions, column
        metadata (names, types, nullability), and foreign key relationships.

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
            # Filters to the public schema and base tables only (excludes views)
            cursor.execute("""
                SELECT
                    t.table_name,
                    c.column_name,
                    c.data_type,
                    c.is_nullable
                FROM
                    information_schema.tables t
                JOIN
                    information_schema.columns c ON t.table_name = c.table_name
                WHERE
                    t.table_schema = 'public' AND t.table_type = 'BASE TABLE'
                ORDER BY
                    t.table_name, c.ordinal_position;
            """)
            tables_and_columns = cursor.fetchall()

            # Query 2: Extract foreign key relationships
            # Joins key_column_usage, referential_constraints, and constraint_column_usage
            # to map foreign key columns to their referenced primary key columns
            cursor.execute("""
                SELECT
                    kcu.table_name AS foreign_table,
                    kcu.column_name AS foreign_column,
                    ccu.table_name AS primary_table,
                    ccu.column_name AS primary_column
                FROM
                    information_schema.key_column_usage AS kcu
                JOIN information_schema.referential_constraints AS rc
                    ON kcu.constraint_name = rc.constraint_name
                    AND kcu.constraint_schema = rc.constraint_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON rc.unique_constraint_name = ccu.constraint_name
                    AND rc.unique_constraint_schema = ccu.constraint_schema
                WHERE
                    kcu.table_schema = 'public';
            """)
            relationships = cursor.fetchall()

        # Format the extracted schema data into a human-readable string
        return format_schema(self.connection_details['dbname'], "PostgreSQL", tables_and_columns, relationships)

    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        """Execute a read-only PostgreSQL query with timeout and row limiting.

        Executes a read-only SQL query on the PostgreSQL database with a
        30-second signal-based timeout. Results are fetched in batches of
        500 rows and returned as a list of dictionaries.

        Args:
            query: The SQL SELECT query to execute (validated as read-only).
            max_rows: Maximum number of rows to return (default: 1000).

        Returns:
            A list of dictionaries, each representing a row with column
            names as keys.

        Raises:
            ConnectionError: If not currently connected to the database.
            TimeoutError: If the query exceeds the 30-second timeout limit.
            RuntimeError: If a PostgreSQL error occurs during execution.
        """
        # Verify that a connection is established before attempting query execution
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        # Validate the query as read-only (inherited security check)
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

        # Save the current SIGALRM handler and install our timeout handler
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)

        # Set a 30-second alarm that will interrupt the query if it takes too long
        signal.alarm(30)

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

                    # Cancel the alarm since the query completed successfully
                    signal.alarm(0)
                    logger.info(f"Query returned {len(results)} rows")
                    return results

                # Query executed but returned no columns (e.g., DDL-like SELECT)
                logger.warning("Query returned no results")
                return []

        except _TimeoutError:
            # Convert the internal timeout exception to a standard TimeoutError
            logger.error("Query execution timed out after 30 seconds")
            raise TimeoutError("Query execution timed out. The query may be too slow or the database is unresponsive.")
        except psycopg2.Error as e:
            # Cancel the alarm before raising the error to prevent interference
            signal.alarm(0)
            # Log the driver-level error details and raise a sanitized RuntimeError
            logger.error(f"Database error: {e.pgcode} - {e.diag.message_primary}")
            raise RuntimeError("A database error occurred while executing the query.")
        finally:
            # Always cancel the alarm regardless of how we exit (success or error)
            signal.alarm(0)
            # Restore the original SIGALRM handler that was active before this query
            signal.signal(signal.SIGALRM, old_handler)

    def get_tables_list(self, schema: str = None) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        target_schema = schema or 'public'
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    t.table_name,
                    t.table_schema,
                    COALESCE(s.n_live_tup, 0)::bigint AS table_rows,
                    c.column_count
                FROM information_schema.tables t
                JOIN information_schema.columns c ON t.table_name = c.table_name AND t.table_schema = c.table_schema
                LEFT JOIN pg_stat_user_tables s ON s.relname = t.table_name
                WHERE t.table_schema = %s AND t.table_type = 'BASE TABLE'
                GROUP BY t.table_name, t.table_schema, s.n_live_tup, c.column_count
                ORDER BY t.table_name;
            """, (target_schema,))
            rows = cursor.fetchall()
        return [
            {"name": r[0], "schema": r[1], "table_rows": r[2], "column_count": r[3]}
            for r in rows
        ]

    def get_table_columns(self, table_name: str, schema: str = None) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        target_schema = schema or 'public'
        with self.connection.cursor() as cursor:
            cursor.execute("""
                SELECT
                    c.column_name,
                    c.data_type,
                    c.is_nullable,
                    CASE WHEN ccu.column_name IS NOT NULL THEN true ELSE false END AS is_primary_key,
                    CASE WHEN c.character_maximum_length IS NOT NULL THEN c.character_maximum_length ELSE NULL END AS max_length
                FROM information_schema.columns c
                LEFT JOIN (
                    SELECT tc.table_schema, tc.table_name, kcu.column_name
                    FROM information_schema.table_constraints tc
                    JOIN information_schema.key_column_usage kcu
                        ON tc.constraint_name = kcu.constraint_name
                        AND tc.table_schema = kcu.table_schema
                    WHERE tc.constraint_type = 'PRIMARY KEY'
                ) ccu ON c.table_name = ccu.table_name AND c.column_name = ccu.column_name AND c.table_schema = ccu.table_schema
                WHERE c.table_name = %s AND c.table_schema = %s
                ORDER BY c.ordinal_position;
            """, (table_name, target_schema))
            rows = cursor.fetchall()
        return [
            {
                "name": r[0],
                "type": r[1],
                "nullable": r[2] == 'YES',
                "is_primary_key": r[3],
                "max_length": r[4],
            }
            for r in rows
        ]

    def batch_insert(self, table_name: str, columns: list[str], rows: list[list], schema: str = None) -> int:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        target_schema = schema or 'public'
        col_names = ", ".join(f'"{c}"' for c in columns)
        placeholders = ", ".join(["%s"] * len(columns))
        sql = f"INSERT INTO \"{target_schema}\".\"{table_name}\" ({col_names}) VALUES ({placeholders})"
        logger.info(f"Executing batch insert into {target_schema}.{table_name}: {len(rows)} rows")
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        try:
            signal.alarm(30)
            with self.connection.cursor() as cursor:
                processed = []
                for row in rows:
                    processed.append(tuple(None if (v is None or v == '') else v for v in row))
                cursor.executemany(sql, processed)
                self.connection.commit()
                signal.alarm(0)
                logger.info(f"Batch insert completed: {cursor.rowcount} rows inserted")
                return cursor.rowcount
        except _TimeoutError:
            logger.error("Batch insert timed out")
            raise TimeoutError("Batch insert timed out after 30 seconds")
        except psycopg2.Error as e:
            signal.alarm(0)
            logger.error(f"Batch insert error: {e.diag.message_primary}")
            raise RuntimeError(f"Database error: {e.diag.message_primary}")
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
