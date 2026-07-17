import pyodbc
from .base import DatabaseStrategy
from ..utils.formatters import format_schema

class MSSQLStrategy(DatabaseStrategy):
    """Strategy for analyzing a Microsoft SQL Server database."""

    def connect(self):
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}} ;"
                f"SERVER={self.connection_details['host']};"
                f"DATABASE={self.connection_details['dbname']};"
                f"UID={self.connection_details['user']};"
                f"PWD={self.connection_details['password']}"
            )
            self.connection = pyodbc.connect(conn_str)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MSSQL. Ensure ODBC Driver 17 for SQL Server is installed. Error: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

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

        with self.connection.cursor() as cursor:
            cursor.execute(cleaned)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    # MSSQL via pyodbc sometimes returns rows as tuples that need clean conversion
                    results.append(dict(zip(columns, row)))
                return results
            return []
