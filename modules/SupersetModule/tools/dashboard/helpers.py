"""Layout JSON builders for dashboard generation.

Internal helpers for _build_simple_layout_json and _build_robust_layout_json
used by the generate_dashboard function.
"""
import json
from typing import List

from modules.SupersetModule import rules


def _build_simple_layout_json(chart_ids: List[int]) -> str:
    """
    Build a simple row layout JSON string from a list of chart IDs.

    Internal helper for generate_dashboard that creates a flat row/column
    layout without fetching chart metadata from the server.

    Args:
        chart_ids: List of chart IDs to arrange in the layout.

    Returns:
        JSON string of the position_json layout.
    """
    chart_info = []
    for cid in chart_ids:
        chart_info.append({
            "id": cid,
            "name": f"Chart {cid}"
        })
    from modules.SupersetModule.tools.dashboard.layout import _build_simple_layout
    layout = _build_simple_layout(chart_info, "row_of_charts", 6, 50)
    return json.dumps(layout)


def _build_robust_layout_json(chart_ids: List[int]) -> str:
    """
    Build a robust nested layout JSON string from a list of chart IDs.

    Internal helper for generate_dashboard that creates a hierarchical
    layout with auto-sizing without fetching chart metadata.

    Args:
        chart_ids: List of chart IDs to arrange in the layout.

    Returns:
        JSON string of the position_json layout.
    """
    chart_info = []
    for cid in chart_ids:
        chart_info.append({
            "id": cid,
            "name": f"Chart {cid}"
        })
    layout = rules.generate_robust_dashboard_layout(chart_info)
    return json.dumps(layout)
