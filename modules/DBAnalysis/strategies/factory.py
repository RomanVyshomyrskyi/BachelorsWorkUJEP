from .base import DatabaseStrategy

def get_db_strategy(db_type: str, connection_details: dict) -> DatabaseStrategy:
    if db_type == "postgres":
        from .postgres import PostgresStrategy
        return PostgresStrategy(connection_details)
    elif db_type in ("mariadb", "mysql"):
        from .mariadb import MariaDBStrategy
        return MariaDBStrategy(connection_details)
    elif db_type == "mssql":
        try:
            from .mssql import MSSQLStrategy
            return MSSQLStrategy(connection_details)
        except ImportError as e:
            raise ImportError(f"MSSQL support requires pyodbc and unixODBC: {e}")
    else:
        raise ValueError(f"Unsupported database type: {db_type}")