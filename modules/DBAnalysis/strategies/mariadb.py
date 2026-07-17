import mysql.connector
from .base import DatabaseStrategy
from ..utils.formatters import format_schema

class MariaDBStrategy(DatabaseStrategy):
    """Strategy for analyzing a MariaDB/MySQL database."""

    def connect(self):
        try:
            self.connection = mysql.connector.connect(
                database=self.connection_details['dbname'],
                user=self.connection_details['user'],
                password=self.connection_details['password'],
                host=self.connection_details['host'],
                port=self.connection_details.get('port', 3306)
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to MariaDB: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        db_name = self.connection_details['dbname']
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
                    results.append(dict(zip(columns, row)))
                return results
            return []
