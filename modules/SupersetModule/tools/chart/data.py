"""
Chart data helpers: _test_chart_data_endpoint, get_chart_data, get_chart_preview.

Contains functions for testing chart data endpoints and retrieving chart data/previews.
"""

import json
import logging
from typing import Dict, Any
from typing import Union
import httpx
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import ChartError
from modules.SupersetModule.schemas.chart import ChartPreviewResponse

from .helpers import logger

logger = logging.getLogger(__name__)


async def _test_chart_data_endpoint(
    manager,
    server_id: str,
    chart_id: int
) -> Dict[str, Any]:
    """
    Test a chart's data endpoint to verify it returns valid data without errors.

    Calls GET /api/v1/chart/{id}/data/ and checks multiple indicators of
    chart health. This is used both pre-creation (via chart validation)
    and post-creation to verify charts actually render.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to test.

    Returns:
        Dict with keys:
          - is_valid (bool): True if chart data endpoint is healthy
          - error (str|None): Error message if invalid, None if valid
          - row_count (int|None): Number of rows returned by the chart query
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return {"is_valid": False, "error": "Server context not found", "row_count": None}

    try:
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}/data/")

        if resp.status_code != 200:
            logger.warning(
                "Chart %s data endpoint HTTP %s body=%s",
                chart_id, resp.status_code, str(resp.text)[:1000],
            )
            return {"is_valid": False, "error": f"HTTP {resp.status_code}: {resp.text[:300]}", "row_count": None}

        data = resp.json()
        result = data.get("result", {})
        error = result.get("error")
        status = result.get("status", "unknown")
        row_count = result.get("sql_rowcount")

        if error:
            logger.warning("Chart %s data endpoint error field: %s", chart_id, str(error)[:500])
            return {"is_valid": False, "error": f"Data endpoint error: {error}", "row_count": row_count}

        if status != "success":
            return {"is_valid": False, "error": f"Data endpoint status: {status}", "row_count": row_count}

        if not row_count or row_count == 0:
            return {"is_valid": False, "error": "Chart returned no data rows (sql_rowcount=0)", "row_count": 0}

        resp_lower = str(resp.text).lower()
        error_keywords = ["does not exist", "doesn't exist", "cannot compile", "undefined",
                          "db engine error", "data error", "error:", "exception:",
                          "traceback", "may not be null", "field may not be",
                          "not found", "is null", "noneType", "can't access",
                          "duplicate", "not subscriptable", "is not defined",
                          "is undefined", "label", "datetime column not provided",
                          "not provided as part", "rendering the visualization"]
        matches = [kw for kw in error_keywords if kw in resp_lower]
        if matches:
            logger.warning(
                "Chart %s data endpoint errors: keywords=%s raw=%s",
                chart_id, matches, str(resp.text)[:1000],
            )
            return {"is_valid": False, "error": f"Chart response contains error keywords: {matches}", "row_count": row_count}

        return {"is_valid": True, "error": None, "row_count": row_count}

    except httpx.HTTPStatusError as e:
        return {"is_valid": False, "error": f"HTTP {e.response.status_code}: {e.response.text[:300]}", "row_count": None}
    except Exception as e:
        return {"is_valid": False, "error": f"Data endpoint exception: {str(e)[:300]}", "row_count": None}


async def get_chart_preview(
    manager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_preview - Get a visual preview URL for a chart.

    Generates URLs for previewing a chart in Superset's Explore interface or
    embedded in other pages. Useful for sharing chart links or embedding charts
    in external dashboards.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart to preview.

    Returns:
        JSON string containing:
          - preview_url: URL to view the chart in Superset's Explore interface
          - chart_id: The chart ID
          - embed_url: URL suitable for embedding in external pages
        Returns ChartError JSON if the server is not found.

    Examples:
        result = await get_chart_preview(manager, "default", chart_id=123)
        # Returns JSON with preview_url and embed_url for chart viewing.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       base_url = ctx.config.base_url.rstrip("/")
       preview_url = f"{base_url}/explore/?slice_id={chart_id}"
       embed_url = f"{base_url}/superset/slice/{chart_id}/"

       return ChartPreviewResponse(
           preview_url=preview_url,
           chart_id=int(chart_id),
           embed_url=embed_url,
       ).model_dump_json(indent=2)
    except Exception as e:
       return ChartError(f"Unexpected error getting chart preview: {e}", details=str(e)).to_json()


async def get_chart_data(
    manager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_chart_data - Fetch underlying data for a chart.

    Calls the chart's data endpoint to retrieve the raw data that the chart
    visualizes. Useful for debugging chart rendering issues, exporting data,
    or analyzing the query results that power a visualization.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric (or string) ID of the chart whose data to fetch.

    Returns:
        JSON string containing the chart's data from GET /api/v1/chart/{id}/data/,
            including the data rows, SQL query, row count, and execution metadata.
        Returns ChartError JSON if the request fails.

    Examples:
        result = await get_chart_data(manager, "default", chart_id=123)
        # Returns JSON with chart query data rows, SQL, row count, and metadata.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       endpoint = f"/api/v1/chart/{chart_id}/data/"
       resp = await execute_request(ctx, "GET", endpoint)
       resp.raise_for_status()
       return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
       return ChartError(
           f"HTTP {e.response.status_code} getting chart data",
           status_code=e.response.status_code,
           details=e.response.text,
       ).to_json()
    except Exception as e:
       return ChartError(f"Unexpected error getting chart data: {e}", details=str(e)).to_json()
