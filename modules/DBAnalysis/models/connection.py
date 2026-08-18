"""
Connection Details Model - Pydantic model for database connection parameters.

Provides a validated data model for database connection credentials used
across all database strategies and MCP tools in the DBAnalysis module.
"""

from pydantic import BaseModel, Field, field_validator


class ConnectionDetails(BaseModel):
    """
    Pydantic model for database connection details with built-in validation.

    This model holds the credentials and connection parameters needed to
    establish a database connection. It is used by MCP tools to validate
    input parameters and by database strategies to configure connections.
        All fields except port are required (min_length=1) to prevent
        incomplete connection attempts. Port is optional and defaults to
        the database-specific default when not specified.

    Attributes:
        host: Database server hostname or IP address (required).
        user: Database authentication username (required).
        password: Database authentication password (required).
        dbname: Name of the target database (required).
        port: Database server port number (optional, database-specific default applied).

    Examples:
        >>> details = ConnectionDetails(
        ...     host="localhost",
        ...     user="admin",
        ...     password="secret",
        ...     dbname="mydb",
        ...     port=5432
        ... )
        >>> details.model_dump()
        {'host': 'localhost', 'user': 'admin', 'password': 'secret', 'dbname': 'mydb', 'port': 5432}
    """

    host: str = Field(..., description="Database host, e.g., localhost", min_length=1)
    """The hostname or IP address of the database server."""

    user: str = Field(..., description="Database user", min_length=1)
    """The username for database authentication."""

    password: str = Field(..., description="Database password", min_length=1)
    """The password for database authentication."""

    dbname: str = Field(..., description="Database name", min_length=1)
    """The name of the database to connect to."""

    port: int | None = Field(None, description="Database port, e.g., 5432")
    """The port number for the database server. Defaults to database-specific default when None."""
