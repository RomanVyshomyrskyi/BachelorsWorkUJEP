"""
Chart metadata: list_charts, get_chart_info, get_standard_chart_params, get_chart_creation_rules.

Contains functions for listing charts, getting chart metadata, and retrieving
standard parameters and creation rules.
"""

import json
import logging
from typing import Optional, Union
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule import rules

logger = logging.getLogger(__name__)


async def list_charts(manager, server_id: str) -> str:
    """
    MCP Tool: superset_list_charts - List all charts on a Superset server.

    Fetches the paginated list of all charts from the Superset API.
    Useful for discovering existing charts and their IDs before creating
    dashboards or making updates.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        JSON string containing the paginated list of charts from GET /api/v1/chart/,
        including each chart's ID, name, viz_type, and datasource info.

    Example:
        result = await list_charts(manager, "default")
        # Returns JSON paginated list of all charts with IDs, names, and viz_types.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/")


async def get_chart_info(
    manager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_info - Get detailed information about a specific chart.

    Fetches the complete configuration and metadata for a single chart, including
    its viz_type, params (as JSON), datasource reference, slice name, and description.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart to inspect.

    Returns:
        JSON string containing the full chart details from GET /api/v1/chart/{id},
        including slice_name, viz_type, params, datasource_id, datasource_type,
        and other metadata.

    Example:
        result = await get_chart_info(manager, "default", chart_id=123)
        # Returns JSON with full chart details: slice_name, viz_type, params, datasource, etc.
    """
    return await impl_superset_api(
       manager, server_id, "GET", f"/api/v1/chart/{chart_id}"
    )


def get_standard_chart_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
    """
    MCP Tool: superset_get_standard_chart_params - Get standard params for a viz type.

    Returns a JSON object with sensible default parameters for the given visualization
    type and datasource. These defaults include required fields and typical values
    that work with most datasets. Use this as a starting point when building chart
    configuration, then customize as needed.

    Args:
        viz_type: The chart visualization type (e.g., 'echarts_bar', 'echarts_line',
            'table', 'pivot_table', 'time_table').
        datasource_id: The ID of the dataset to use. Used to populate dataset-specific
            defaults like available metrics and column references.
        overrides_json: Optional JSON string of parameter overrides that replace
            the default values. Use this to set specific values while keeping
            the rest of the defaults.

    Returns:
        JSON string of the standard parameters for the given viz_type and datasource.
            This can be used as the base for chart creation or exploration.

    Example:
        result = get_standard_chart_params("echarts_bar", datasource_id=42)
        # Returns JSON with default params like metrics, groupby, and viz_type for the chart type.
    """
    overrides = json.loads(overrides_json) if overrides_json else {}
    params = rules.get_standard_chart_params(viz_type, datasource_id, **overrides)
    return json.dumps(params, indent=2)


def get_chart_creation_rules() -> str:
    """
    MCP Tool: superset_get_chart_creation_rules - Get expert rules for creating charts.

    Returns a set of expert guidelines and best practices for creating functional
    Superset charts. These rules cover common pitfalls, required fields per chart
    type, and tips for ensuring charts render correctly.

    Returns:
        String containing the expert rules for chart creation, formatted as
            readable text with guidelines organized by topic.

    Example:
        result = get_chart_creation_rules()
        # Returns string with expert guidelines for creating charts.
    """
    return rules.get_chart_creation_rules()
