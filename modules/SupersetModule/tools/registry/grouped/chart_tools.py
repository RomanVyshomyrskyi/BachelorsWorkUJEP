"""
Chart-related tool registration helpers.

Contains the tool registration functions for Superset chart operations:
- superset_get_chart_api_info
- superset_get_standard_chart_params
- superset_get_chart_creation_rules
- list_charts
- get_chart_info
- generate_chart
- get_chart_preview
- get_chart_data
- get_chart_type_schema
- superset_get_all_chart_schemas
- superset_update_chart
"""
from typing import List, Optional, Union
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import charts


def register_chart_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all chart management tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="superset_get_chart_api_info")
    async def tool_get_chart_api_info(server_id: str) -> str:
        """Retrieves metadata about the chart API from _info endpoint (filters, permissions, properties)."""
        return await charts.get_chart_api_info(manager, server_id)

    @mcp.tool(name="superset_get_standard_chart_params")
    def tool_get_standard_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
        """Returns standard chart params for a viz type to prevent empty query errors."""
        return charts.get_standard_chart_params(viz_type, datasource_id, overrides_json)

    @mcp.tool(name="superset_get_chart_creation_rules")
    def tool_get_chart_rules() -> str:
        """Returns expert rules for creating functional charts."""
        return charts.get_chart_creation_rules()

    @mcp.tool(name="list_charts")
    async def tool_list_charts(server_id: str) -> str:
        """Lists all charts on a server. GET /api/v1/chart/."""
        return await charts.list_charts(manager, server_id)

    @mcp.tool(name="get_chart_info")
    async def tool_get_chart_info(server_id: str, chart_id: Union[int, str]) -> str:
        """Gets detailed information for a specific chart by ID."""
        return await charts.get_chart_info(manager, server_id, chart_id)

    @mcp.tool(name="generate_chart")
    async def tool_generate_chart(server_id: str, dataset_id: int, config: str, slice_name: Optional[str] = None, description: Optional[str] = None) -> str:
        """Create and save a new chart. Use generate_explore_link for ad-hoc exploration."""
        return await charts.generate_chart(manager, server_id, dataset_id, config, slice_name, description)

    @mcp.tool(name="get_chart_preview")
    async def tool_get_chart_preview(server_id: str, chart_id: Union[int, str]) -> str:
        """Get a visual preview URL for a chart."""
        return await charts.get_chart_preview(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_data")
    async def tool_get_chart_data(server_id: str, chart_id: Union[int, str]) -> str:
        """Get underlying chart data in text-friendly format."""
        return await charts.get_chart_data(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_type_schema")
    async def tool_get_chart_type_schema(server_id: str, chart_type: str) -> str:
        """Get schema for a specific chart type (expected params/config)."""
        return await charts.get_chart_type_schema(manager, server_id, chart_type)

    @mcp.tool(name="superset_get_all_chart_schemas")
    async def tool_get_all_chart_schemas(server_id: str) -> str:
        """Discover ALL chart types from Superset and return a consolidated Markdown reference. Use BEFORE generating charts to get the complete, up-to-date list of chart types with their required parameters. Cached for 24 hours."""
        return await charts.get_all_chart_schemas(manager, server_id)

    @mcp.tool(name="superset_update_chart")
    async def tool_update_chart(server_id: str, chart_id: int, json_body: str) -> str:
        """Updates an existing chart. json_body contains fields to update."""
        return await charts.update_chart(manager, server_id, chart_id, json_body)
