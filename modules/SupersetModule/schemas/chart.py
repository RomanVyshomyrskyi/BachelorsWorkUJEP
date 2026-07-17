from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChartListItem(BaseModel):
    id: int
    slice_name: Optional[str] = None
    viz_type: Optional[str] = None
    datasource_id: Optional[int] = None
    datasource_type: Optional[str] = None
    description: Optional[str] = None
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    url: Optional[str] = None


class ChartDetail(BaseModel):
    id: int
    slice_name: Optional[str] = None
    viz_type: Optional[str] = None
    datasource_id: Optional[int] = None
    datasource_type: Optional[str] = None
    description: Optional[str] = None
    params: Optional[Any] = None
    dashboards: List[Dict[str, Any]] = Field(default_factory=list)
    changed_on: Optional[str] = None
    created_on: Optional[str] = None
    changed_by: Optional[Dict[str, Any]] = None
    created_by: Optional[Dict[str, Any]] = None
    owners: List[Dict[str, Any]] = Field(default_factory=list)
    tags: List[Dict[str, Any]] = Field(default_factory=list)
    url: Optional[str] = None


class ChartCreatePayload(BaseModel):
    slice_name: str
    viz_type: str
    datasource_id: int
    datasource_type: str = "table"
    params: str = "{}"
    description: Optional[str] = None
    dashboards: Optional[List[int]] = None


class ChartUpdatePayload(BaseModel):
    slice_name: Optional[str] = None
    viz_type: Optional[str] = None
    params: Optional[str] = None
    description: Optional[str] = None
    dashboards: Optional[List[int]] = None
    datasource_id: Optional[int] = None
    datasource_type: Optional[str] = None


class ChartGeneratePayload(BaseModel):
    dataset_id: int
    config: Dict[str, Any] = Field(default_factory=dict)
    slice_name: Optional[str] = None
    save_chart: bool = True
    description: Optional[str] = None


class ChartPreviewResponse(BaseModel):
    preview_url: str
    chart_id: int
    embed_url: Optional[str] = None


class ChartDataResponse(BaseModel):
    chart_id: int
    data: List[Dict[str, Any]] = Field(default_factory=list)
    columns: List[str] = Field(default_factory=list)
    row_count: int = 0
    status: Optional[str] = None


class ChartTypeSchema(BaseModel):
    chart_type: str
    schema_data: Dict[str, Any] = Field(default_factory=dict)
