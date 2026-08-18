"""
Chart schema discovery: get_chart_type_schema, get_all_chart_schemas, get_chart_api_info.

Contains functions for discovering and retrieving chart type schemas from the Superset API.
"""

import os
import json
import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import ChartError
from modules.SupersetModule.schemas.chart import ChartTypeSchema
from modules.SupersetModule.chart_strategies import TYPE_MAP
from .helpers import CACHE_DIR, CACHE_FILE, CACHE_TTL_SECONDS
from . import schema_helpers

logger = logging.getLogger(__name__)


async def get_chart_api_info(manager, server_id: str) -> str:
    """
    MCP Tool: superset_get_chart_api_info - Retrieves metadata about the chart API.

    Fetches the chart API's _info endpoint which contains metadata about
    supported chart types, available filters, permissions, and API properties.
    Useful for understanding what chart types and features are available
    on a specific Superset instance.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        JSON string containing the chart API metadata from /api/v1/chart/_info,
        including supported viz_types, form_data schemas, and feature flags.

    Examples:
        result = await get_chart_api_info(manager, "default")
        # Returns JSON with chart API metadata including available viz_types and filters.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")


async def get_chart_type_schema(
    manager,
    server_id: str,
    chart_type: str
) -> str:
    """
    MCP Tool: superset_get_chart_type_schema - Get schema for a specific chart type.

    Fetches the JSON schema for a specific chart type's parameters from the Superset API.
    The schema describes all valid parameters, their types, required fields, and default
    values. Useful for understanding what configuration options are available for a
    particular chart type.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        chart_type: The Superset viz_type to get the schema for (e.g., 'echarts_bar',
            'echarts_timeseries_line', 'table').

    Returns:
        JSON string containing the chart type schema with the chart_type name and
        the raw schema object from the Superset API. Returns ChartError JSON if
            the schema cannot be retrieved.

    Examples:
        result = await get_chart_type_schema(manager, "default", chart_type="echarts_bar")
        # Returns JSON schema describing all valid params for the chart type.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        result = await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
        )
        return ChartTypeSchema(chart_type=chart_type, schema_data={"raw": result}).model_dump_json(indent=2)
    except Exception as e:
        return ChartError(f"Unexpected error getting chart type schema: {e}", details=str(e)).to_json()


async def get_all_chart_schemas(manager, server_id: str) -> str:
    """
    Dynamically discovers ALL chart types from Superset API,
    fetches each schema, and returns a consolidated Markdown reference.
        Calls the chart _info endpoint to discover all registered viz_types,
        then fetches the full JSON schema for each type. Results are parsed
        into categorized field lists (required, metric, groupby/dimension,
        other) and formatted as a Markdown reference document including a
        quick-reference table and detailed per-chart-type sections.

        Results are cached on disk for 24 hours to avoid repeated API calls.
        The cache is stored at ``.cache/chart_schemas.json`` in the module
        directory.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to query.

    Returns:
        A Markdown string containing the complete chart type reference with
        required fields, metric fields, groupby fields, and other fields
            for every chart type available on the Superset instance.

    Examples:
        result = await get_all_chart_schemas(manager, "default")
        # Returns Markdown reference with required/metric/groupby fields for all chart types.
    """
    async def _fetch_schema(chart_type: str) -> Optional[Dict[str, Any]]:
        """Fetch the JSON schema for a single chart type from Superset API."""
        try:
            result = await impl_superset_api(
                manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
            )
            return {"type": chart_type, "schema": json.loads(result)}
        except Exception:
            return None

    # --- Main logic ---
    ctx = manager.get_context(server_id)
    if not ctx:
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Check cache for previously fetched schemas (24-hour TTL)
    if os.path.isfile(CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("markdown", json.dumps(cached, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch chart API info to discover all chart types
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception as e:
        return ChartError(f"Failed to fetch chart API info: {e}", details=str(e)).to_json()

    # Extract chart type names from _info response
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        fd = properties.get("form_data", {})
        if isinstance(fd, dict):
            fd_props = fd.get("properties", {})
            viz_type = fd_props.get("viz_type", {})
            if isinstance(viz_type, dict):
                enum_vals = viz_type.get("enum", [])
                if enum_vals:
                    chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            form_data_prop = properties.get("form_data", {})
            if isinstance(form_data_prop, dict):
                fd_viz = form_data_prop.get("viz_type", {})
                if isinstance(fd_viz, dict):
                    enum_vals = fd_viz.get("enum", [])
                    if enum_vals:
                        chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            ct = properties.get("chart_types", [])
            if isinstance(ct, list) and ct:
                chart_types = [str(c) for c in ct]

        if not chart_types:
            for key, val in properties.items():
                if isinstance(val, dict) and "enum" in val:
                    enum_vals = val.get("enum", [])
                    if isinstance(enum_vals, list) and len(enum_vals) > 2:
                        chart_types = [str(v) for v in enum_vals]
                        break

    if not chart_types:
        chart_types = list(TYPE_MAP.values())
        chart_types = list(set(chart_types))
        chart_types.sort()

    # Fetch schemas for all chart types in parallel
    tasks = [_fetch_schema(ct) for ct in chart_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results, building parsed schema entries for each chart type
    all_schemas = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result is None:
            continue
        try:
            parsed = schema_helpers.parse_schema(result["schema"])
            all_schemas.append({
                "type": result["type"],
                "parsed": parsed,
                "raw_schema": result["schema"],
            })
        except Exception:
            all_schemas.append({
                "type": result["type"],
                "parsed": {"required": [], "metric_fields": [], "groupby_fields": [], "other_fields": ["Schema parsing failed"]},
                "raw_schema": {},
            })

    all_schemas.sort(key=lambda x: x["type"])

    cache_key = f"Superset {info_data.get('result', {}).get('version', 'unknown')}"
    markdown = schema_helpers.build_markdown(all_schemas, cache_key)

    # Write cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "cache_key": cache_key,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "total_types": len(all_schemas),
                "chart_types": [s["type"] for s in all_schemas],
                "markdown": markdown,
            }, f, indent=2)
    except OSError:
        pass

    return markdown
