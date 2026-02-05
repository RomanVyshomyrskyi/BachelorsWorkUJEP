import psycopg2
from .base import DatabaseStrategy
from ..utils.formatters import format_schema

class PostgresStrategy(DatabaseStrategy):
    """Strategy for analyzing a PostgreSQL database."""

    def connect(self):
        try:
            self.connection = psycopg2.connect(
                dbname=self.connection_details['dbname'],
                user=self.connection_details['user'],
                password=self.connection_details['password'],
                host=self.connection_details['host'],
                port=self.connection_details.get('port', 5432)
            )
        except Exception as e:
            raise ConnectionError(f"Failed to connect to PostgreSQL: {e}")

    def disconnect(self):
        if self.connection:
            self.connection.close()
        self.connection = None

    def get_schema_representation(self) -> str:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")

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

    def execute_query(self, query: str) -> list[dict]:
        if not self.connection:
            raise ConnectionError("Not connected to the database.")
        
        # Basic security check
        if not query.strip().upper().startswith("SELECT"):
             raise ValueError("Security violation: Only SELECT queries are allowed.")

        with self.connection.cursor() as cursor:
            cursor.execute(query)
            if cursor.description:
                columns = [desc[0] for desc in cursor.description]
                results = []
                for row in cursor.fetchall():
                    results.append(dict(zip(columns, row)))
                return results
            return []
