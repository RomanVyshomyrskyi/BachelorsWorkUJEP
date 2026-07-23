"""
Pydantic schemas for Apache Superset chart API interactions.

Defines models for chart listing, detail views, creation/update payloads,
preview responses, data retrieval, and chart type schema introspection.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ChartListItem(BaseModel):
    """
    Lightweight chart summary for list views (e.g., chart index).

    Used in paginated chart listing responses where full detail
    (like params JSON) is not needed. Contains only essential identity and metadata.
    """
    id: int  # Unique chart/slice ID in Superset
    slice_name: Optional[str] = None  # Display name of the chart
    viz_type: Optional[str] = None  # Visualization type (e.g., "table", "bar", "pie")
    datasource_id: Optional[int] = None  # ID of the underlying dataset
    datasource_type: Optional[str] = None  # Type of datasource (e.g., "table")
    description: Optional[str] = None  # Chart description text
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    url: Optional[str] = None  # Direct URL to view the chart


class ChartDetail(BaseModel):
    """
    Full chart details including params, dashboards, ownership, and tags.

    Used when fetching a single chart by ID for editing or inspection.
    Contains all chart properties plus linked dashboard references and metadata.
    """
    id: int  # Unique chart/slice ID
    slice_name: Optional[str] = None  # Display name of the chart
    viz_type: Optional[str] = None  # Visualization type
    datasource_id: Optional[int] = None  # ID of the underlying dataset
    datasource_type: Optional[str] = None  # Type of datasource
    description: Optional[str] = None  # Chart description
    params: Optional[Any] = None  # Full chart parameters as JSON/dict
    dashboards: List[Dict[str, Any]] = Field(default_factory=list)  # Dashboards this chart appears in
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    changed_by: Optional[Dict[str, Any]] = None  # User who last modified the chart
    created_by: Optional[Dict[str, Any]] = None  # User who created the chart
    owners: List[Dict[str, Any]] = Field(default_factory=list)  # Owners of this chart
    tags: List[Dict[str, Any]] = Field(default_factory=list)  # Tags assigned to this chart
    url: Optional[str] = None  # Direct URL to view the chart


class ChartCreatePayload(BaseModel):
    """
    Request payload for creating a new chart via the Superset API.

    Used when programmatically generating a chart from a dataset.
    Requires at minimum a dataset reference and visualization type.
    """
    slice_name: str  # Name for the new chart
    viz_type: str  # Visualization type to render (e.g., "table", "pivot_table_v2")
    datasource_id: int  # Dataset ID to base the chart on
    datasource_type: str = "table"  # Type of datasource (default: "table")
    params: str = "{}"  # Chart configuration as JSON string
    description: Optional[str] = None  # Optional chart description
    dashboards: Optional[List[int]] = None  # Optional list of dashboard IDs to link the chart to


class ChartUpdatePayload(BaseModel):
    """
    Request payload for updating an existing chart's properties.

    All fields are optional to support partial updates via PATCH semantics.
    Only provided fields will be modified in the Superset chart.
    """
    slice_name: Optional[str] = None  # Updated chart name
    viz_type: Optional[str] = None  # Updated visualization type
    params: Optional[str] = None  # Updated chart parameters JSON
    description: Optional[str] = None  # Updated chart description
    dashboards: Optional[List[int]] = None  # Updated list of dashboard IDs to link
    datasource_id: Optional[int] = None  # Updated dataset ID
    datasource_type: Optional[str] = None  # Updated datasource type


class ChartGeneratePayload(BaseModel):
    """
    Payload for programmatically generating a chart from a dataset and config.

    Used by the generate_chart automation tool. Accepts a dataset reference
    and a configuration dict to define the chart's appearance and data.
    """
    dataset_id: int  # Dataset ID to build the chart from
    config: Dict[str, Any] = Field(default_factory=dict)  # Chart configuration parameters
    slice_name: Optional[str] = None  # Optional name for the generated chart
    save_chart: bool = True  # Whether to save the chart (True) or just preview (False)
    description: Optional[str] = None  # Optional description for the generated chart


class ChartPreviewResponse(BaseModel):
    """
    Response from generating a chart preview without saving.

    Returned when save_chart=False in ChartGeneratePayload.
    Provides a URL to view the generated chart visualization.
    """
    preview_url: str  # URL to view the chart preview
    chart_id: int  # ID of the temporary or saved chart
    embed_url: Optional[str] = None  # URL for embedding the chart elsewhere


class ChartDataResponse(BaseModel):
    """
    Underlying data retrieved from a chart's query.

    Returned when fetching the raw data that a chart visualizes.
    Contains the data rows, column metadata, row count, and status.
    """
    chart_id: int  # ID of the chart the data belongs to
    data: List[Dict[str, Any]] = Field(default_factory=list)  # Data rows as dicts
    columns: List[str] = Field(default_factory=list)  # Column names in the result
    row_count: int = 0  # Total number of rows returned
    status: Optional[str] = None  # Query execution status (e.g., "success", "running")


class ChartTypeSchema(BaseModel):
    """
    Schema information for a specific chart/visualization type.

    Returned when introspecting what parameters a chart type (e.g., "bar", "pie")
    accepts. Contains the type name and its schema definition.
    """
    chart_type: str  # The visualization type name (e.g., "bar", "line", "table")
    schema_data: Dict[str, Any] = Field(default_factory=dict)  # Schema/params for this chart type
