from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatasetListItem(BaseModel):
    id: int
    table_name: Optional[str] = None
    schema: Optional[str] = None
    database_id: Optional[int] = None
    database_name: Optional[str] = None
    sql: Optional[str] = None
    description: Optional[str] = None
    changed_on: Optional[str] = None
    created_on: Optional[str] = None


class DatasetDetail(BaseModel):
    id: int
    table_name: Optional[str] = None
    schema: Optional[str] = None
    description: Optional[str] = None
    sql: Optional[str] = None
    database: Optional[Dict[str, Any]] = None
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    metrics: List[Dict[str, Any]] = Field(default_factory=list)
    owners: List[Dict[str, Any]] = Field(default_factory=list)
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    changed_by: Optional[Dict[str, Any]] = None
    created_by: Optional[Dict[str, Any]] = None
    datasource_type: Optional[str] = None


class VirtualDatasetCreatePayload(BaseModel):
    dataset_name: str
    database_id: int
    sql: str
    schema: Optional[str] = None
    description: Optional[str] = None
    columns: Optional[List[Dict[str, Any]]] = None
    metrics: Optional[List[Dict[str, Any]]] = None


class PhysicalDatasetCreatePayload(BaseModel):
    table_name: str
    database_id: int
    schema: Optional[str] = None
    owners: Optional[List[int]] = None
    metrics: Optional[List[Dict[str, Any]]] = None
    columns: Optional[List[Dict[str, Any]]] = None
    sql_expression: Optional[str] = None


class DatabaseSchemaResponse(BaseModel):
    database_id: int
    database_name: Optional[str] = None
    engine: Optional[str] = None
    tables: List[Dict[str, Any]] = Field(default_factory=list)
