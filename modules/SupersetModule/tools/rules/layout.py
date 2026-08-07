"""Layout generation rules for Superset dashboard creation.

Provides the generate_robust_dashboard_layout() function that builds
a hierarchical position_json with ROOT→GRID→ROW→CHART hierarchy.
This prevents "Cannot read properties of undefined" errors that
occur when charts are placed directly under GRID_ID.
"""

import json
import uuid
from typing import Any, Dict, List


def generate_robust_dashboard_layout(chart_info: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a robust position_json for Superset.

    Description:
        Builds a nested layout dictionary that enforces the ROOT → GRID → ROW →
        CHART hierarchy required by Superset's frontend. Charts are grouped into
        rows of 2 (6 columns each in a 12-column Bootstrap grid) to ensure
        proper responsive layout.

        The ROOT→GRID→ROW→CHART hierarchy is mandatory because Superset's
        dashboard rendering engine iterates children of GRID_ID expecting ROW
        containers. Placing a CHART directly under GRID_ID causes "Cannot read
        properties of undefined (reading 'length')" errors.

    Args:
        chart_info: List of dicts, each with:
            - 'id' (int): The chart's numerical ID in Superset.
            - 'name' (str): The chart's human-readable slice name.

    Returns:
        A position_json dict with the following structure:
        {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW-R0-xxx", ...], "parents": ["ROOT_ID"]},
            "ROW-R0-xxx": {"type": "ROW", "id": "ROW-R0-xxx", "children": ["CHART-xxx-42"], "parents": ["GRID_ID"], "meta": {...}},
            "CHART-xxx-42": {"type": "CHART", "id": "CHART-xxx-42", "children": [], "parents": ["ROW-R0-xxx"], "meta": {"chartId": 42, ...}},
            ...
        }
    """
    dashboard_uuid = str(uuid.uuid4())[:8]

    layout = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
    }

    rows = [chart_info[i : i + 2] for i in range(0, len(chart_info), 2)]

    for row_idx, row_charts in enumerate(rows):
        row_id = f"ROW-R{row_idx}-{dashboard_uuid}"
        layout["GRID_ID"]["children"].append(row_id)

        layout[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [],
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }

        for chart_idx, chart in enumerate(row_charts):
            chart_cid = f"CHART-{dashboard_uuid}-{chart['id']}"
            layout[row_id]["children"].append(chart_cid)

            layout[chart_cid] = {
                "type": "CHART",
                "id": chart_cid,
                "children": [],
                "parents": [row_id],
                "meta": {
                    "chartId": chart["id"],
                    "height": 50,
                    "width": 6,
                    "sliceName": chart["name"],
                },
            }

    return layout
