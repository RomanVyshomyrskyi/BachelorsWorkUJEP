"""
Update chart operation: update_chart.

Updates an existing chart's configuration via the Superset API.
"""

import logging
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api

logger = logging.getLogger(__name__)


async def update_chart(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int,
    json_body: str
) -> str:
    """
    MCP Tool: superset_update_chart - Update an existing chart's configuration.

    Sends a PUT request to the Superset chart API to modify a chart's settings
    such as name, params, description, or other properties.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to update.
        json_body: JSON string containing the fields to update. See Superset API
            docs for the chart model structure. Only the fields included in this
            JSON will be modified.

    Returns:
        JSON string containing the updated chart's details from the API response,
        or an error JSON if the update fails.

    Example:
        result = await update_chart(
            manager, "default", chart_id=123,
            json_body='{"slice_name": "Updated Sales Chart"}'
        )
        # Returns JSON with updated chart details.
    """
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{chart_id}", json_body=json_body)
