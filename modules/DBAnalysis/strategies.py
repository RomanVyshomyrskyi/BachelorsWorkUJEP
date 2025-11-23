# modules/DBAnalysis/strategies.py
import psycopg2
import mysql.connector
import pyodbc
from .interfaces import DatabaseStrategy

def format_schema(db_name: str, db_type: str, tables_and_columns: list, relationships: list) -> str:
    """Helper function to format the schema into a readable string."""
    schema_str = f"SCHEMA FOR {db_type.upper()} DATABASE '{db_name}':\n\n"
    
    current_table = None
    for row in tables_and_columns:
        table_name, column_name, data_type, is_nullable = row
        if table_name != current_table:
            schema_str += f"TABLE: {table_name}\n"
            current_table = table_name
        schema_str += f"  COLUMN: {column_name}, TYPE: {data_type}, NULLABLE: {is_nullable}\n"
    
    schema_str += "\nRELATIONSHIPS:\n"
    if relationships:
        for rel in relationships:
            fk_table, fk_column, pk_table, pk_column = rel
            schema_str += f"  {fk_table}.{fk_column} -> {pk_table}.{pk_column}\n"
    else:
        schema_str += "  No foreign key relationships found.\n"
        
    return schema_str


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
            # Get tables and columns
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
            
            # Get foreign key relationships
            cursor.execute("""
                SELECT
                    kcu.table_name AS foreign_table,
                    kcu.column_name AS foreign_column,
                    ccu.table_name AS primary_table,
                    ccu.column_name AS primary_column
                FROM
                    information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name AND ccu.table_schema = tc.table_schema
                WHERE tc.constraint_type = 'FOREIGN KEY' AND tc.table_schema = 'public';
            """)
            relationships = cursor.fetchall()

        return format_schema(self.connection_details['dbname'], "PostgreSQL", tables_and_columns, relationships)


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
            cursor.execute(f"""
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
                    t.table_schema = '{db_name}' AND t.table_type = 'BASE TABLE'
                ORDER BY
                    t.table_name, c.ordinal_position;
            """,)
            tables_and_columns = cursor.fetchall()
            
            cursor.execute(f"""
                SELECT
                    kcu.table_name AS foreign_table,
                    kcu.column_name AS foreign_column,
                    kcu.referenced_table_name AS primary_table,
                    kcu.referenced_column_name AS primary_column
                FROM
                    information_schema.key_column_usage AS kcu
                WHERE
                    kcu.table_schema = '{db_name}' AND kcu.referenced_table_name IS NOT NULL;
            """,)
            relationships = cursor.fetchall()

        return format_schema(db_name, "MariaDB", tables_and_columns, relationships)


class MSSQLStrategy(DatabaseStrategy):
    """Strategy for analyzing a Microsoft SQL Server database."""

    def connect(self):
        try:
            conn_str = (
                f"DRIVER={{ODBC Driver 17 for SQL Server}} প্রশিক্ষক
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


def get_db_strategy(db_type: str, connection_details: dict) -> DatabaseStrategy:
    """
    Factory function to select the appropriate database strategy.
    """
    if db_type == "postgres":
        return PostgresStrategy(connection_details)
    elif db_type == "mariadb":
        return MariaDBStrategy(connection_details)
    elif db_type == "mssql":
        return MSSQLStrategy(connection_details)
    else:
        raise ValueError(f"Unsupported database type: {db_type}")