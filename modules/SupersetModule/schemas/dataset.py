"""
Pydantic schemas for Apache Superset dataset API interactions.

Defines models for dataset listing, detail views, creation payloads
(for both virtual and physical datasets), and database schema responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetListItem(BaseModel):
    """
    Lightweight dataset summary for list/index views.

    Used in paginated dataset listing responses. Contains only essential
    identity and metadata without full column or metric definitions.
    """
    id: int  # Unique dataset ID in Superset
    table_name: Optional[str] = None  # Name of the underlying table or query alias
    schema: Optional[str] = None  # Database schema name (e.g., "public", "analytics")
    database_id: Optional[int] = None  # ID of the database this dataset belongs to
    database_name: Optional[str] = None  # Human-readable database name
    sql: Optional[str] = None  # SQL query for virtual datasets
    description: Optional[str] = None  # Dataset description text
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp


class DatasetDetail(BaseModel):
    """
    Full dataset details including columns, metrics, and ownership.

    Used when fetching a single dataset by ID. Contains all column definitions,
    computed metrics, ownership info, and datasource type classification.
    """
    id: int  # Unique dataset ID
    table_name: Optional[str] = None  # Name of the underlying table or query alias
    schema: Optional[str] = None  # Database schema name
    description: Optional[str] = None  # Dataset description
    sql: Optional[str] = None  # SQL query (for virtual datasets)
    database: Optional[Dict[str, Any]] = None  # Database object details
    columns: List[Dict[str, Any]] = Field(default_factory=list)  # Column definitions with types and metadata
    metrics: List[Dict[str, Any]] = Field(default_factory=list)  # Computed metric definitions
    owners: List[Dict[str, Any]] = Field(default_factory=list)  # Owners of this dataset
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    changed_by: Optional[Dict[str, Any]] = None  # User who last modified the dataset
    created_by: Optional[Dict[str, Any]] = None  # User who created the dataset
    datasource_type: Optional[str] = None  # Type: "table" for physical, "query" for virtual


class VirtualDatasetCreatePayload(BaseModel):
    """
    Request payload for creating a virtual dataset from a SQL query.

    Used by the create_virtual_dataset automation tool. Takes a raw SQL
    SELECT statement and registers it as a dataset for charting.
    """
    dataset_name: str  # Display name for the virtual dataset
    database_id: int  # Database ID where the SQL query will be executed
    sql: str  # SQL SELECT query to define the dataset
    schema: Optional[str] = None  # Optional database schema for query resolution
    description: Optional[str] = None  # Optional dataset description
    columns: Optional[List[Dict[str, Any]]] = None  # Optional explicit column definitions
    metrics: Optional[List[Dict[str, Any]]] = None  # Optional computed metric definitions


class PhysicalDatasetCreatePayload(BaseModel):
    """
    Request payload for registering a physical database table as a dataset.

    Used by the create_dataset automation tool. Wraps a database table
    reference in a Superset dataset with optional custom columns and metrics.
    """
    table_name: str  # Name of the physical table in the database
    database_id: int  # Database ID where the table resides
    schema: Optional[str] = None  # Optional schema name (defaults to public)
    owners: Optional[List[int]] = None  # Optional list of owner user IDs
    metrics: Optional[List[Dict[str, Any]]] = None  # Optional metric definitions to add
    columns: Optional[List[Dict[str, Any]]] = None  # Optional column overrides
    sql_expression: Optional[str] = None  # Optional custom SQL expression for derived columns


class DatabaseSchemaResponse(BaseModel):
    """
    Response containing database schema metadata with its tables.

    Used when introspecting a database's schema structure. Returns
    the database identity (ID, name, engine) and a list of table definitions.
    """
    database_id: int  # ID of the database being inspected
    database_name: Optional[str] = None  # Human-readable database name
    engine: Optional[str] = None  # Database engine type (e.g., "postgresql", "mssql")
    tables: List[Dict[str, Any]] = Field(default_factory=list)  # List of table metadata in the database
