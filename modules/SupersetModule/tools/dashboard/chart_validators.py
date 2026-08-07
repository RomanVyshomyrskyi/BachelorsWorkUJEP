"""Chart validation helpers for Superset dashboard operations.

Provides functions for validating chart existence, data endpoints,
and pre-validating charts before dashboard creation.
"""
import json
from typing import List, Dict, Any, Optional

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request


async def _validate_charts_exist(manager: ConnectionManager, server_id: str, chart_ids: List[int]) -> List[int]:
    """
    Validate that all chart IDs exist on the Superset server.

        Returns list of chart IDs that were not found.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return chart_ids

    all_charts = []
    page = 1
    page_size = 100

    while True:
        try:
            resp = await ctx.client.get("/api/v1/chart/", params={"page_size": page_size, "page": page})
            if resp.status_code != 200:
                break
            data = resp.json().get("result", [])
            if not data:
                break
            all_charts.extend(data)
            if len(data) < page_size:
                break
            page += 1
        except Exception:
            break

    existing_ids = {c["id"] for c in all_charts}
    return [cid for cid in chart_ids if cid not in existing_ids]


async def _validate_chart_data_endpoint(manager: ConnectionManager, server_id: str, chart_id: int) -> Dict[str, Any]:
    """
    Test a single chart's data endpoint to verify it actually renders.

    Delegates to the blunt version in charts.py that blocks on ANY sign of trouble.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to test.

    Returns:
        Dict with is_valid, error, row_count, and viz_type keys.
    """
    from modules.SupersetModule.tools.charts import _test_chart_data_endpoint
    result = await _test_chart_data_endpoint(manager, server_id, chart_id)
    result["viz_type"] = None
    return result


async def _get_chart_info(manager: ConnectionManager, server_id: str, chart_id: int) -> Optional[Dict[str, Any]]:
    """Get chart info including viz_type from Superset API.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_id: The numeric ID of the chart to inspect.

    Returns:
        Dict with id, viz_type, and slice_name keys, or None if the chart
        cannot be retrieved.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return None

    try:
        resp = await execute_request(ctx, "GET", f"/api/v1/chart/{chart_id}")
        chart = resp.json().get("result", {})
        return {
            "id": chart.get("id"),
            "viz_type": chart.get("viz_type"),
            "slice_name": chart.get("slice_name"),
        }
    except Exception:
        return None


async def _pre_validate_chart_data(manager: ConnectionManager, server_id: str, chart_ids: List[int]) -> List[Dict[str, Any]]:
    """
    Pre-validate all charts before dashboard creation by testing their data endpoints.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_ids: List of chart IDs to validate.

    Returns:
        List of validation result dicts for failed charts, each with chart_id,
        viz_type, slice_name, and error keys. Empty list means all valid.
    """
    failed_charts = []

    for chart_id in chart_ids:
        chart_info = await _get_chart_info(manager, server_id, chart_id)
        viz_type = chart_info.get("viz_type", "unknown") if chart_info else "unknown"
        slice_name = chart_info.get("slice_name", f"Chart {chart_id}") if chart_info else f"Chart {chart_id}"

        validation = await _validate_chart_data_endpoint(manager, server_id, chart_id)

        if not validation["is_valid"]:
            failed_charts.append({
                "chart_id": chart_id,
                "viz_type": viz_type,
                "slice_name": slice_name,
                "error": validation["error"],
            })

    return failed_charts
