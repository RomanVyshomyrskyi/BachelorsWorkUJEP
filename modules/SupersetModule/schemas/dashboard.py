"""
Pydantic schemas for Apache Superset dashboard API interactions.

Defines models for dashboard listing, detail views, creation/update payloads,
chart linking results, and dashboard generation responses.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class DashboardListItem(BaseModel):
    """
    Lightweight dashboard summary for list/index views.

    Used in paginated dashboard listing responses. Contains only essential
    identity and metadata without position/layout details.
    """
    id: int  # Unique dashboard ID in Superset
    dashboard_title: Optional[str] = None  # Display title of the dashboard
    slug: Optional[str] = None  # URL-friendly slug for the dashboard
    published: bool = False  # Whether the dashboard is published (visible to users)
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    url: Optional[str] = None  # Direct URL to view the dashboard


class DashboardDetail(BaseModel):
    """
    Full dashboard details including layout, charts, ownership, and roles.

    Used when fetching a single dashboard by ID. Contains the position JSON
    for layout, list of charts, and access control metadata.
    """
    id: int  # Unique dashboard ID
    dashboard_title: Optional[str] = None  # Display title
    slug: Optional[str] = None  # URL-friendly slug
    position_json: Optional[Any] = None  # JSON layout configuration for dashboard widgets
    json_metadata: Optional[Any] = None  # Additional JSON metadata (e.g., tags, description)
    published: bool = False  # Whether the dashboard is published
    charts: List[Dict[str, Any]] = Field(default_factory=list)  # Charts embedded in this dashboard
    owners: List[Dict[str, Any]] = Field(default_factory=list)  # Owners of this dashboard
    roles: List[Dict[str, Any]] = Field(default_factory=list)  # Roles with access to this dashboard
    changed_on: Optional[str] = None  # Last modified timestamp
    created_on: Optional[str] = None  # Creation timestamp
    changed_by: Optional[Dict[str, Any]] = None  # User who last modified the dashboard
    created_by: Optional[Dict[str, Any]] = None  # User who created the dashboard
    url: Optional[str] = None  # Direct URL to view the dashboard


class DashboardCreatePayload(BaseModel):
    """
    Request payload for creating a new dashboard via the Superset API.

    Requires at minimum a title. Position JSON, slug, metadata,
    owners, and roles are all optional (position defaults to empty layout).
    """
    dashboard_title: str  # Display title for the new dashboard
    position_json: str = "{}"  # JSON string defining widget positions and layout
    slug: Optional[str] = None  # URL-friendly slug (auto-generated if omitted)
    json_metadata: Optional[str] = None  # Additional metadata as JSON string
    owners: List[int] = Field(default_factory=list)  # List of user IDs who own the dashboard
    roles: List[int] = Field(default_factory=list)  # List of role IDs with access
    published: bool = False  # Whether to publish immediately (default: draft)


class DashboardUpdatePayload(BaseModel):
    """
    Request payload for updating an existing dashboard's properties.

    All fields are optional to support partial updates via PATCH semantics.
    Only provided fields will be modified in the Superset dashboard.
    """
    dashboard_title: Optional[str] = None  # Updated dashboard title
    position_json: Optional[str] = None  # Updated layout JSON
    slug: Optional[str] = None  # Updated URL slug
    json_metadata: Optional[str] = None  # Updated metadata JSON
    published: Optional[bool] = None  # Toggle published state
    owners: Optional[List[int]] = None  # Updated list of owner user IDs
    roles: Optional[List[int]] = None  # Updated list of access role IDs


class ChartLinkResult(BaseModel):
    """
    Result of adding a chart to a dashboard.

    Used when linking a chart to an existing dashboard via bulk or single link.
    Reports success/failure with an optional message.
    """
    dashboard_id: int  # ID of the dashboard the chart was linked to
    chart_id: int  # ID of the chart that was linked
    success: bool = True  # Whether the linking operation succeeded
    message: str = ""  # Status message or error description


class DashboardGenerateResponse(BaseModel):
    """
    Response from generating a new dashboard with charts.

    Returned when creating a dashboard programmatically with pre-existing charts.
    Contains the new dashboard ID, title, URL, and the chart IDs included.
    """
    id: int  # ID of the newly created dashboard
    dashboard_title: str  # Title of the new dashboard
    url: Optional[str] = None  # Direct URL to view the new dashboard
    chart_ids: List[int] = Field(default_factory=list)  # Chart IDs included in the dashboard
