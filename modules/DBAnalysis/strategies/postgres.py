import logging
import signal
import psycopg2
from .base import DatabaseStrategy, MAX_ROWS
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)


class _TimeoutError(Exception):
    pass


def _timeout_handler(signum, frame):
    raise _TimeoutError("Query execution timed out")


class PostgresStrategy(DatabaseStrategy):
    """Strategy for analyzing a PostgreSQL database."""

    def connect(self):
        db = self.connection_details
        logger.info(f"Connecting to PostgreSQL at {db['host']}:{db.get('port', 5432)}/{db['dbname']}")
        try:
            self.connection = psycopg2.connect(
                dbname=db['dbname'],
                user=db['user'],
                password=db['password'],
                host=db['host'],
                port=db.get('port', 5432)
            )
            # Set statement timeout in milliseconds (30 seconds)
            self.connection.set_session(timeout=30000)
            logger.info(f"Connected to PostgreSQL: {db['dbname']}")
        except Exception as e:
            logger.error(f"PostgreSQL connection failed: {e}")
            raise ConnectionError("Failed to connect to database. Please verify your credentials and network.")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info("PostgreSQL connection closed")
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        logger.info(f"Extracting schema for {self.connection_details['dbname']}")
        with self.connection.cursor() as cursor:
            # 1. Get tables and columns
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
            
            # 2. Get Foreign Keys (using information_schema)
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

        return format_schema(self.connection_details['dbname'], "PostgreSQL", tables_and_columns, relationships)

    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

        # Set up timeout using signal
        old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(30)  # 30 second timeout

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(cleaned)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    # Use fetchmany for efficient pagination
                    results = []
                    while True:
                        batch = cursor.fetchmany(500)
                        if not batch:
                            break
                        for row in batch:
                            results.append(dict(zip(columns, row)))
                            if len(results) >= max_rows:
                                break
                        if len(results) >= max_rows:
                            break
                    
                    signal.alarm(0)  # Cancel the alarm
                    logger.info(f"Query returned {len(results)} rows")
                    return results
                logger.warning("Query returned no results")
                return []
        except _TimeoutError:
            logger.error("Query execution timed out after 30 seconds")
            raise TimeoutError("Query execution timed out. The query may be too slow or the database is unresponsive.")
        except psycopg2.Error as e:
            signal.alarm(0)  # Cancel the alarm
            logger.error(f"Database error: {e.pgcode} - {e.diag.message_primary}")
            raise RuntimeError("A database error occurred while executing the query.")
        finally:
            signal.alarm(0)  # Ensure alarm is cancelled
            signal.signal(signal.SIGALRM, old_handler)
