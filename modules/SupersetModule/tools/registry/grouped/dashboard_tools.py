"""
Dashboard-related tool registration helpers.

Contains the tool registration functions for Superset dashboard operations:
- superset_generate_simple_dashboard_layout
- superset_create_dashboard
- superset_get_dashboard_api_info
- superset_update_dashboard
- superset_bulk_link_charts_to_dashboard
- superset_generate_robust_dashboard_layout
- generate_dashboard
- add_chart_to_existing_dashboard
- get_dashboard_info
- superset_get_dashboard_creation_rules
"""
import json
from typing import List, Optional
from fastmcp import FastMCP

from modules.SupersetModule.exceptions import DashboardError
from modules.SupersetModule.log_utils import LogCollector
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import dashboards

_log = LogCollector(__name__)


def _handle_chart_ids(chart_ids: Optional[List[int]], body: Optional[dict]) -> Optional[List[int]]:
    """Extract chart_ids from body fallback if not provided directly.

    Args:
        chart_ids: The chart_ids parameter value.
        body: Optional body dict that may contain chart_ids.

    Returns:
        The chart_ids list, or None if not found (triggering error).
    """
    if chart_ids is None and body:
        val = body.get("chart_ids")
        if val:
            chart_ids = val if isinstance(val, list) else []
    return chart_ids


def _chart_ids_required_error() -> str:
    """Return a standardized error JSON when chart_ids is required but missing."""
    return _log.collect(DashboardError("chart_ids is required.").to_json())


def register_dashboard_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all dashboard tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="superset_generate_simple_dashboard_layout")
    async def tool_generate_simple_dashboard_layout(server_id: str, chart_ids: List[int] = None, layout_type: str = "row_of_charts", chart_width: int = 6, chart_height: int = 50, body: Optional[dict] = None) -> str:
        """Generates a valid position_json arranging charts in a simple row/column layout."""
        chart_ids = _handle_chart_ids(chart_ids, body)
        if chart_ids is None:
            return _chart_ids_required_error()
        return await dashboards.generate_simple_dashboard_layout(manager, server_id, chart_ids, layout_type, chart_width, chart_height)

    @mcp.tool(name="superset_create_dashboard")
    async def tool_create_dashboard(server_id: str, dashboard_title: str, position_json: str, slug: Optional[str] = None, json_metadata: Optional[str] = None, owners: Optional[List[int]] = None, roles: Optional[List[int]] = None, published: Optional[bool] = False) -> str:
        """Creates a new dashboard on a Superset server."""
        return await dashboards.create_dashboard(manager, server_id, dashboard_title, position_json, slug, json_metadata, owners, roles, published)

    @mcp.tool(name="superset_get_dashboard_api_info")
    async def tool_get_dashboard_api_info(server_id: str) -> str:
        """Retrieves metadata about the dashboard API from _info endpoint."""
        return await dashboards.get_dashboard_api_info(manager, server_id)

    @mcp.tool(name="superset_update_dashboard")
    async def tool_update_dashboard(server_id: str, dashboard_id: int, json_body: str) -> str:
        """Updates an existing dashboard. json_body contains fields to update."""
        return await dashboards.update_dashboard(manager, server_id, dashboard_id, json_body)

    @mcp.tool(name="superset_bulk_link_charts_to_dashboard")
    async def tool_bulk_link_charts(server_id: str, dashboard_id: int, chart_ids: List[int] = None, body: Optional[dict] = None) -> str:
        """Links multiple charts to a dashboard in bulk."""
        chart_ids = _handle_chart_ids(chart_ids, body)
        if chart_ids is None:
            return _chart_ids_required_error()
        return await dashboards.bulk_link_charts(manager, server_id, dashboard_id, chart_ids)

    @mcp.tool(name="superset_generate_robust_dashboard_layout")
    async def tool_generate_robust_layout(server_id: str, chart_ids: List[int] = None, body: Optional[dict] = None) -> str:
        """Generates a nested position_json with ROOT→GRID→ROW→CHART hierarchy."""
        chart_ids = _handle_chart_ids(chart_ids, body)
        if chart_ids is None:
            return _chart_ids_required_error()
        return await dashboards.generate_robust_layout(manager, server_id, chart_ids)

    @mcp.tool(name="generate_dashboard")
    async def tool_generate_dashboard(
        server_id: str,
        dashboard_title: str,
        chart_ids: Optional[str] = None,
        slug: Optional[str] = None,
        json_metadata: Optional[str] = None,
        published: bool = False,
        layout_type: str = "robust",
        body: Optional[dict] = None,
    ) -> str:
        """Create a new dashboard from chart IDs with auto-generated layout."""
        parsed_ids = []
        if chart_ids:
            stripped = chart_ids.strip()
            if stripped.startswith("["):
                try:
                    parsed_ids = json.loads(stripped)
                    if not isinstance(parsed_ids, list):
                        parsed_ids = []
                    else:
                        parsed_ids = [int(x) for x in parsed_ids]
                except (json.JSONDecodeError, ValueError, TypeError):
                    parsed_ids = []
            elif "," in stripped:
                try:
                    parsed_ids = [int(x.strip()) for x in stripped.split(",") if x.strip()]
                except ValueError:
                    parsed_ids = []
            else:
                try:
                    parsed_ids = [int(stripped)]
                except ValueError:
                    parsed_ids = []

        if not parsed_ids:
            parsed_ids = _handle_chart_ids(chart_ids, body)
            if parsed_ids is None:
                return _chart_ids_required_error()

        return await dashboards.generate_dashboard(manager, server_id, dashboard_title, parsed_ids, slug, json_metadata, published, layout_type)

    @mcp.tool(name="add_chart_to_existing_dashboard")
    async def tool_add_chart_to_existing_dashboard(server_id: str, dashboard_id: int, chart_id: int) -> str:
        """Add a chart to an existing dashboard. Preferred over generate_dashboard for existing dashboards."""
        return await dashboards.add_chart_to_existing_dashboard(manager, server_id, dashboard_id, chart_id)

    @mcp.tool(name="get_dashboard_info")
    async def tool_get_dashboard_info(server_id: str, dashboard_id: int) -> str:
        """Gets detailed information for a specific dashboard by ID."""
        return await dashboards.get_dashboard_info(manager, server_id, dashboard_id)

    @mcp.tool(name="superset_get_dashboard_creation_rules")
    def tool_get_dashboard_rules() -> str:
        """Returns expert rules for creating functional dashboards."""
        return dashboards.get_dashboard_creation_rules()
