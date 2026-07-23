"""
Pydantic schemas for Apache Superset SQL Lab interactions.

Defines models for SQL query execution payloads, query results, saved
queries (create/detail), and SQL Lab URL generation responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SqlQueryExecutePayload(BaseModel):
    """
    Request payload for executing a SQL query via Superset SQL Lab API.

    Used by the sqllab_execute_query and run_read_only_sql automation tools.
    Specifies the target database, the SQL statement, and optional session context.
    """
    database_id: int  # Target database ID to execute the query against
    sql: str  # SQL SELECT statement to execute
    schema: Optional[str] = None  # Optional database schema for query resolution
    client_id: Optional[str] = None  # Optional client/session identifier for tracking
    tab_name: Optional[str] = None  # Optional tab name in SQL Lab UI


class SqlQueryResult(BaseModel):
    """
    Result from executing a SQL query through Superset SQL Lab.

    Contains the query metadata, returned data rows, column definitions,
    row count, and execution status including any error messages.
    """
    query_id: int  # Unique query execution ID assigned by SQL Lab
    client_id: str  # Client/session identifier matching the request
    status: str = ""  # Execution status (e.g., "success", "running", "error")
    data: List[Dict[str, Any]] = Field(default_factory=list)  # Result rows as key-value dicts
    columns: List[Dict[str, Any]] = Field(default_factory=list)  # Column metadata dicts
    row_count: int = 0  # Total number of rows in the result set
    sql: str = ""  # The SQL query that was executed
    error: Optional[str] = None  # Error message if execution failed
    completed: bool = False  # Whether the query execution has finished


class SavedQueryCreatePayload(BaseModel):
    """
    Request payload for saving a SQL query to the Saved Queries list.

    Used by the save_sql_query automation tool. Stores a query for
    reuse and sharing with other Superset users.
    """
    database_id: int  # Database this saved query applies to
    label: str  # Display name for the saved query
    sql: str  # The SQL query to save
    schema: Optional[str] = None  # Optional database schema for the saved query
    description: Optional[str] = None  # Optional description of what the query does


class SavedQueryDetail(BaseModel):
    """
    Full details of a saved SQL query from Superset.

    Used when listing or fetching saved queries. Contains the query
    text, labels, metadata, and audit timestamps.
    """
    id: int  # Unique saved query ID
    label: str  # Display name of the saved query
    sql: str  # The saved SQL query text
    database_id: Optional[int] = None  # Database ID the query applies to
    schema: Optional[str] = None  # Database schema for the query
    description: Optional[str] = None  # Query description
    created_on: Optional[str] = None  # Creation timestamp
    changed_on: Optional[str] = None  # Last modified timestamp


class SqlLabUrlResponse(BaseModel):
    """
    Response containing a SQL Lab URL with pre-filled query.

    Returned when generating a SQL Lab link with context. The URL opens
    SQL Lab with the specified database and query pre-populated.
    """
    url: str  # The generated SQL Lab URL with pre-filled query
    database_id: int  # Database ID the URL targets
    sql: Optional[str] = None  # The SQL query included in the URL
    schema: Optional[str] = None  # Database schema specified in the URL
