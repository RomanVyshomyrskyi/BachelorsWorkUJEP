import logging
import mysql.connector
from .base import DatabaseStrategy, MAX_ROWS
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)


class MariaDBStrategy(DatabaseStrategy):
    """Strategy for analyzing a MariaDB/MySQL database."""

    def connect(self):
        db = self.connection_details
        logger.info(f"Connecting to MariaDB/MySQL at {db['host']}:{db.get('port', 3306)}/{db['dbname']}")
        try:
            self.connection = mysql.connector.connect(
                database=db['dbname'],
                user=db['user'],
                password=db['password'],
                host=db['host'],
                port=db.get('port', 3306),
                # Disable multi-statement execution at driver level
                raw=False,
            )
            # Set statement timeout (MySQL/MariaDB uses seconds)
            self.connection.cmd_set_system_variable('max_execution_time', '30000')
            logger.info(f"Connected to MariaDB/MySQL: {db['dbname']}")
        except Exception as e:
            logger.error(f"MariaDB/MySQL connection failed: {e}")
            raise ConnectionError("Failed to connect to database. Please verify your credentials and network.")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info("MariaDB/MySQL connection closed")
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        db_name = self.connection_details['dbname']
        logger.info(f"Extracting schema for {db_name}")
        with self.connection.cursor() as cursor:
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

        return format_schema(db_name, "MariaDB", tables_and_columns, relationships)

    def execute_query(self, query: str, max_rows: int = MAX_ROWS) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

        try:
            with self.connection.cursor() as cursor:
                cursor.execute(cleaned)
                if cursor.description:
                    columns = [desc[0] for desc in cursor.description]
                    results = []
                    # Use fetchmany for efficient pagination with row limit
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
                    
                    logger.info(f"Query returned {len(results)} rows")
                    return results
                logger.warning("Query returned no results")
                return []
        except mysql.connector.Error as e:
            logger.error(f"Database error: {e.errno} - {e.msg}")
            raise RuntimeError("A database error occurred while executing the query.")
