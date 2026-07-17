from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SqlQueryExecutePayload(BaseModel):
    database_id: int
    sql: str
    schema: Optional[str] = None
    client_id: Optional[str] = None
    tab_name: Optional[str] = None


class SqlQueryResult(BaseModel):
    query_id: int
    client_id: str
    status: str = ""
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[Dict[str, Any]] = Field(default_factory=list)
    row_count: int = 0
    sql: str = ""
    error: Optional[str] = None
    completed: bool = False


class SavedQueryCreatePayload(BaseModel):
    database_id: int
    label: str
    sql: str
    schema: Optional[str] = None
    description: Optional[str] = None


class SavedQueryDetail(BaseModel):
    id: int
    label: str
    sql: str
    database_id: Optional[int] = None
    schema: Optional[str] = None
    description: Optional[str] = None
    created_on: Optional[str] = None
    changed_on: Optional[str] = None


class SqlLabUrlResponse(BaseModel):
    url: str
    database_id: int
    sql: Optional[str] = None
    schema: Optional[str] = None
