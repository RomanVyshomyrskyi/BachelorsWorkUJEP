from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardListItem(BaseModel):
    id: int
    dashboard_title: Optional[str] = None
    slug: Optional[str] = None
    published: bool = False
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    url: Optional[str] = None


class DashboardDetail(BaseModel):
    id: int
    dashboard_title: Optional[str] = None
    slug: Optional[str] = None
    position_json: Optional[Any] = None
    json_metadata: Optional[Any] = None
    published: bool = False
    charts: List[Dict[str, Any]] = Field(default_factory=list)
    owners: List[Dict[str, Any]] = Field(default_factory=list)
    roles: List[Dict[str, Any]] = Field(default_factory=list)
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    changed_by: Optional[Dict[str, Any]] = None
    created_by: Optional[Dict[str, Any]] = None
    url: Optional[str] = None


class DashboardCreatePayload(BaseModel):
    dashboard_title: str
    position_json: str = "{}"
    slug: Optional[str] = None
    json_metadata: Optional[str] = None
    owners: List[int] = Field(default_factory=list)
    roles: List[int] = Field(default_factory=list)
    published: bool = False


class DashboardUpdatePayload(BaseModel):
    dashboard_title: Optional[str] = None
    position_json: Optional[str] = None
    slug: Optional[str] = None
    json_metadata: Optional[str] = None
    published: Optional[bool] = None
    owners: Optional[List[int]] = None
    roles: Optional[List[int]] = None


class ChartLinkResult(BaseModel):
    dashboard_id: int
    chart_id: int
    success: bool = True
    message: str = ""


class DashboardGenerateResponse(BaseModel):
    id: int
    dashboard_title: str
    url: Optional[str] = None
    chart_ids: List[int] = Field(default_factory=list)
