"""
Pydantic schemas for Apache Superset database API interactions.

Defines models for database listing, detail views, and schema metadata
introspection. Used for managing database connections in Superset.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatabaseListItem(BaseModel):
    """
    Lightweight database summary for list/index views.

    Used in paginated database listing responses. Contains connection
    identity, backend engine type, and capability flags.
    """
    id: int  # Unique database connection ID in Superset
    database_name: Optional[str] = None  # Display name of the database connection
    backend: Optional[str] = None  # Database engine type (e.g., "postgresql", "mariadb", "mssql")
    allow_dml: bool = False  # Whether DML operations (INSERT/UPDATE/DELETE) are allowed
    allow_multi_schema_metadata_fetch: bool = False  # Whether multi-schema metadata queries are enabled
    expose_in_sqllab: bool = True  # Whether this database appears in SQL Lab
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp


class DatabaseDetail(BaseModel):
    """
    Full database details including connection info, tables, and ownership.

    Used when fetching a single database by ID. Contains the full connection
    configuration, list of tables, owners, and audit metadata.
    """
    id: int  # Unique database connection ID
    database_name: Optional[str] = None  # Display name
    backend: Optional[str] = None  # Database engine type
    allow_dml: bool = False  # Whether DML operations are permitted
    allow_multi_schema_metadata_fetch: bool = False  # Multi-schema metadata query flag
    expose_in_sqllab: bool = True  # Visibility in SQL Lab
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    changed_by: Optional[Dict[str, Any]] = None  # User who last modified the database config
    created_by: Optional[Dict[str, Any]] = None  # User who created the database connection
    owners: List[Dict[str, Any]] = Field(default_factory=list)  # Owners of this database connection
    tables: List[Dict[str, Any]] = Field(default_factory=list)  # Tables visible in this database


class DatabaseSchemaInfo(BaseModel):
    """
    Database schema metadata response with table listing.

    Used when introspecting a database's available schemas and tables.
    Contains database identity and a list of table definitions with metadata.
    """
    database_id: int  # ID of the database being inspected
    database_name: Optional[str] = None  # Human-readable database name
    engine: Optional[str] = None  # Database engine type (e.g., "postgres", "mssql")
    tables: List[Dict[str, Any]] = Field(default_factory=list)  # Table metadata in the database
