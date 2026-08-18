"""
Strategy Factory - Database strategy instantiation and selection.

Provides the get_db_strategy function that implements the Strategy
pattern's factory method, selecting the appropriate database-specific
implementation (PostgresStrategy, MariaDBStrategy, or MSSQLStrategy)
based on the database type string.
"""

from .base import DatabaseStrategy


def get_db_strategy(db_type: str, connection_details: dict) -> DatabaseStrategy:
    """
    Create and return the appropriate database strategy for the given type.

    This factory function implements the Strategy pattern's factory method,
    selecting the correct database-specific implementation based on the
    db_type parameter. Each strategy handles driver-specific connection
    logic while sharing a common interface defined by DatabaseStrategy.

    Strategy Selection Logic:
        - "postgres": Returns PostgresStrategy using psycopg2 driver.
        - "mariadb" or "mysql": Returns MariaDBStrategy using mysql.connector.
        - "mssql": Returns MSSQLStrategy using pyodbc driver.
        - Any other value: Raises ValueError with a descriptive message.

    Lazy Loading:
        Strategy classes are imported inside each branch for lazy loading,
        avoiding unnecessary dependency imports when a particular database
        type is not being used (e.g., MSSQL drivers on non-Windows systems).

    Args:
        db_type: The database type identifier string. Must be one of:
                 "postgres", "mariadb", "mysql", or "mssql".
        connection_details: A dictionary containing connection parameters
                            (host, user, password, dbname, port).

    Returns:
        A DatabaseStrategy instance configured with the provided connection
        details, ready to be used as a context manager.

    Raises:
        ImportError: If MSSQL is requested but pyodbc/unixODBC are not installed.
        ValueError: If db_type is not one of the supported database types.

    Examples:
        >>> details = {"host": "localhost", "user": "admin", "password": "secret",
        ...            "dbname": "mydb", "port": 5432}
        >>> strategy = get_db_strategy("postgres", details)
        >>> with strategy as db:
        ...     results = db.execute_query("SELECT * FROM users")
    """
    # PostgreSQL: use the psycopg2 driver strategy
    if db_type == "postgres":
        from .postgres import PostgresStrategy
        return PostgresStrategy(connection_details)

    # MariaDB and MySQL: share the same mysql.connector driver strategy
    elif db_type in ("mariadb", "mysql"):
        from .mariadb import MariaDBStrategy
        return MariaDBStrategy(connection_details)

    # Microsoft SQL Server: use the pyodbc driver strategy
    # Note: pyodbc and unixODBC must be installed on the system
    elif db_type == "mssql":
        try:
            from .mssql import MSSQLStrategy
            return MSSQLStrategy(connection_details)
        except ImportError as e:
            # Provide a helpful error message explaining the missing dependencies
            raise ImportError(f"MSSQL support requires pyodbc and unixODBC: {e}")

    # Reject unsupported database types with a clear error message
    else:
        raise ValueError(f"Unsupported database type: {db_type}")
