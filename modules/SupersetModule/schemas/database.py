from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DatabaseListItem(BaseModel):
    id: int
    database_name: Optional[str] = None
    backend: Optional[str] = None
    allow_dml: bool = False
    allow_multi_schema_metadata_fetch: bool = False
    expose_in_sqllab: bool = True
    changed_on: Optional[str] = None
    created_on: Optional[str] = None


class DatabaseDetail(BaseModel):
    id: int
    database_name: Optional[str] = None
    backend: Optional[str] = None
    allow_dml: bool = False
    allow_multi_schema_metadata_fetch: bool = False
    expose_in_sqllab: bool = True
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    changed_by: Optional[Dict[str, Any]] = None
    created_by: Optional[Dict[str, Any]] = None
    owners: List[Dict[str, Any]] = Field(default_factory=list)
    tables: List[Dict[str, Any]] = Field(default_factory=list)


class DatabaseSchemaInfo(BaseModel):
    database_id: int
    database_name: Optional[str] = None
    engine: Optional[str] = None
    tables: List[Dict[str, Any]] = Field(default_factory=list)
