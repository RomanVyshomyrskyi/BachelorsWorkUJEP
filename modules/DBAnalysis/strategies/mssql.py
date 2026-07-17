import logging
import pyodbc
from .base import DatabaseStrategy
from ..utils.formatters import format_schema

logger = logging.getLogger(__name__)

class MSSQLStrategy(DatabaseStrategy):
    """Strategy for analyzing a Microsoft SQL Server database."""

    def connect(self):
        db = self.connection_details
        logger.info(f"Connecting to MSSQL at {db['host']}/{db['dbname']}")
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}} ;"
                f"SERVER={db['host']};"
                f"DATABASE={db['dbname']};"
                f"UID={db['user']};"
                f"PWD={db['password']}"
            )
            self.connection = pyodbc.connect(conn_str)
            logger.info(f"Connected to MSSQL: {db['dbname']}")
        except Exception as e:
            logger.error(f"MSSQL connection failed: {e}")
            raise ConnectionError(f"Failed to connect to MSSQL. Ensure ODBC Driver 17 for SQL Server is installed. Error: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            logger.info("MSSQL connection closed")
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

        logger.info(f"Extracting schema for {self.connection_details['dbname']}")
        with self.connection.cursor() as cursor:
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
        
        return format_schema(self.connection_details['dbname'], "MSSQL", tables_and_columns, relationships)

    def execute_query(self, query: str) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        cleaned = self._validate_read_only_query(query)
        logger.info(f"Executing query ({len(cleaned)} chars)")

        with self.connection.cursor() as cursor:
            cursor.execute(cleaned)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    # MSSQL via pyodbc sometimes returns rows as tuples that need clean conversion
                    results.append(dict(zip(columns, row)))
                logger.info(f"Query returned {len(results)} rows")
                return results
            logger.warning("Query returned no results")
            return []
