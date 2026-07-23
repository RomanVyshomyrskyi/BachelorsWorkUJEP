"""
MariaDB/MySQL Strategy - Database operations for MariaDB and MySQL.

Implements the DatabaseStrategy interface for MariaDB and MySQL databases
using the mysql-connector-python driver. Provides connection management,
schema extraction from information_schema, and read-only query execution
with driver-level timeout enforcement.
"""

import logging
import mysql.connector
from .base import DatabaseStrategy, MAX_ROWS
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)


class MariaDBStrategy(DatabaseStrategy):
    """
    Database strategy implementation for MariaDB/MySQL using mysql.connector.

    This strategy provides MariaDB/MySQL-specific connection management,
    schema extraction from information_schema tables, and read-only query
    execution with driver-level timeout enforcement.

    Connection Security:
        - Sets mysql.connector.raw=False to enable parameterized query safety.
        - Uses cmd_set_system_variable('max_execution_time', '30000') to set
          a 30-second statement-level timeout (MySQL-specific feature).
        - Disables multi-statement execution at the driver level (raw=False).

    Schema Extraction:
        - Queries information_schema.tables and information_schema.columns
          for table and column metadata, filtered by database name.
        - Queries information_schema.key_column_usage for foreign key
          relationships where referenced_table_name is not NULL.

    Query Execution:
        - Enforces read-only validation via inherited _validate_read_only_query.
        - Fetches results in batches of 500 rows using fetchmany().
        - Limits results to MAX_ROWS (1000) to prevent memory exhaustion.

    Usage:
        >>> details = {"host": "localhost", "user": "admin", "password": "secret",
        ...            "dbname": "mydb", "port": 3306}
        >>> strategy = MariaDBStrategy(details)
        >>> with strategy as db:
        ...     schema = db.get_schema_representation()
        ...     results = db.execute_query("SELECT * FROM users LIMIT 10")
    """

    def connect(self):
        """
        Establish a connection to the MariaDB/MySQL database.

        Creates a mysql.connector connection using the credentials from
        connection_details, configures statement-level timeout, and
        stores the connection object for subsequent operations.

        Description:
            1. Extracts connection parameters from self.connection_details.
            2. Attempts to establish a mysql.connector connection with the
               given credentials, with raw=False for parameterized safety.
            3. Sets a 30-second max_execution_time using cmd_set_system_variable().
            4. Stores the connection in self.connection on success.
            5. Raises ConnectionError with a user-friendly message on failure.

        Raises:
            ConnectionError: If the connection fails (invalid credentials,
                             unreachable host, wrong port, etc.).
        """
        # Extract connection parameters from the stored details dictionary
        db = self.connection_details

        # Log the connection attempt with server and database information
        logger.info(f"Connecting to MariaDB/MySQL at {db['host']}:{db.get('port', 3306)}/{db['dbname']}")

        try:
            # Establish the mysql.connector connection with the provided credentials
            # raw=False enables parameterized query safety and prevents raw byte returns
            self.connection = mysql.connector.connect(
                database=db['dbname'],
                user=db['user'],
                password=db['password'],
                host=db['host'],
                port=db.get('port', 3306),
                # Disable multi-statement execution at driver level for safety
                raw=False,
            )

            # Set statement-level timeout to 30 seconds (30000 milliseconds)
            # This limits how long any single SQL statement can run on the server
            self.connection.cmd_set_system_variable('max_execution_time', '30000')

            # Log successful connection for audit/debugging purposes
            logger.info(f"Connected to MariaDB/MySQL: {db['dbname']}")
        except Exception as e:
            # Log the full error for debugging and raise a user-friendly ConnectionError
            logger.error(f"MariaDB/MySQL connection failed: {e}")
            raise ConnectionError("Failed to connect to database. Please verify your credentials and network.")

    def disconnect(self):
        """
        Close the MariaDB/MySQL database connection and release resources.

        Description:
            1. Checks if a connection object exists.
            2. Closes the connection if open.
            3. Sets self.connection to None to prevent use-after-close errors.
        """
        # Only attempt to close if a connection object exists
        if self.connection:
            self.connection.close()
            logger.info("MariaDB/MySQL connection closed")
        # Clear the connection reference to prevent use-after-close
        self.connection = None

    def get_schema_representation(self) -> str:
        """
        Extract the MariaDB/MySQL database schema as a formatted string.

        Queries information_schema to retrieve table definitions, column
        metadata (names, types, nullability), and foreign key relationships,
        filtered by the target database name.

        Returns:
            A formatted string with table listings, column details, and
            foreign key relationships.

        Raises:
            ConnectionError: If not currently connected to the database.
        """
        # Verify that a connection is established before attempting schema extraction
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        # Extract the database name for filtering schema queries
        db_name = self.connection_details['dbname']

        # Log the schema extraction operation
        logger.info(f"Extracting schema for {db_name}")

        # Open a cursor and execute schema extraction queries
        with self.connection.cursor() as cursor:
            # Query 1: Extract table names, column names, data types, and nullability
            # Filters by the specific database name using parameterized query
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
                    t.table_schema = %s AND t.table_type = 'BASE TABLE'
                ORDER BY
                    t.table_name, c.ordinal_position;
            """, (db_name,))
            tables_and_columns = cursor.fetchall()

            # Query 2: Extract foreign key relationships
            # Only includes rows where a referenced table exists (no self-referencing without target)
            cursor.execute("""
                SELECT
                    kcu.table_name AS foreign_table,
                    kcu.column_name AS foreign_column,
                    kcu.referenced_table_name AS primary_table,
                    kcu.referenced_column_name AS primary_column
                FROM
                    information_schema.key_column_usage AS kcu
                WHERE
                    kcu.table_schema = %s AND kcu.referenced_table_name IS NOT NULL;
            """, (db_name,))
            relationships = cursor.fetchall()

        # Format the extracted schema data into a human-readable string
        return format_schema(db_name, "MariaDB", tables_and_columns, relationships)

    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        """
        Execute a read-only MariaDB/MySQL query with row limiting.

        This method validates the query as read-only, executes it with a cursor,
        and fetches results in batches.

        Args:
            query: The SQL SELECT query to execute (validated as read-only).
            max_rows: Maximum number of rows to return (default: 1000).

        Returns:
            A list of dictionaries, each representing a row with column names as keys.

        Raises:
            ConnectionError: If not currently connected to the database.
            RuntimeError: If a MariaDB/MySQL error occurs during execution.

        Description:
            1. Validates connection state.
            2. Validates the query as read-only via inherited method.
            3. Executes the query with a cursor.
            4. Fetches results in batches of 500 rows using fetchmany().
            5. Stops fetching once max_rows is reached.
            6. Handles MySQL errors and converts them to RuntimeError.
        """
        # Verify that a connection is established before attempting query execution
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        # Validate the query as read-only (inherited security check)
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

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

        except mysql.connector.Error as e:
            # Log the driver-level error details and raise a sanitized RuntimeError
            logger.error(f"Database error: {e.errno} - {e.msg}")
            raise RuntimeError("A database error occurred while executing the query.")
