"""
Chart types cache management.

Contains _ensure_chart_types_cached and _is_known_chart_type.
"""

import os
import json
import time
import logging
from typing import List
from modules.SupersetModule.chart_strategies import TYPE_MAP
from modules.SupersetModule.tools.general import impl_superset_api

from .helpers import CACHE_DIR, CHART_TYPES_CACHE_FILE, CACHE_TTL_SECONDS

logger = logging.getLogger(__name__)


async def _ensure_chart_types_cached(manager, server_id: str) -> List[str]:
    """
    Ensure chart types cache exists and is fresh.
    Returns list of known chart type names.
    Auto-fetches if cache is missing or expired.
    """
    import asyncio

    # Check cache
    if os.path.isfile(CHART_TYPES_CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CHART_TYPES_CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CHART_TYPES_CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return [t for t in cached.get("chart_types", []) if t != "parallel"]
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch from Superset API
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception:
        # Fallback to local TYPE_MAP
        return list(TYPE_MAP.values())

    # Extract chart types from _info
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        # Check form_data.properties.viz_type.enum
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

    # Filter out chart types not registered on this Superset instance
    CHART_TYPES_BLOCKED = {"parallel"}
    chart_types = [t for t in chart_types if t not in CHART_TYPES_BLOCKED]

    # Save cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CHART_TYPES_CACHE_FILE, "w") as f:
            json.dump({
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "chart_types": chart_types,
            }, f, indent=2)
    except OSError:
        pass

    return chart_types


def _is_known_chart_type(chart_types: List[str], viz_type: str) -> bool:
    """Check if a viz_type is known (either in dynamic cache or local TYPE_MAP)."""
    if viz_type in chart_types:
        return True
    # Also check against local TYPE_MAP values as fallback
    return viz_type in TYPE_MAP.values()
