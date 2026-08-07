"""
Dashboard-to-Mermaid diagram generation.

Provides the dashboard_to_mermaid() function that creates a flowchart
showing a dashboard connected to its constituent chart nodes.

Usage:
    >>> from modules.SupersetModule.tools.mermaid.dashboards import dashboard_to_mermaid
    >>> print(dashboard_to_mermaid("Sales Overview", chart_ids=[1, 2, 3]))
"""
from typing import Any, Dict, List, Optional

from modules.SupersetModule.tools.mermaid.base import _sanitize


def dashboard_to_mermaid(
    dashboard_title: str,
    chart_ids: Optional[List[int]] = None,
    chart_info: Optional[List[Dict[str, Any]]] = None,
) -> str:
    """Generate a Mermaid flowchart showing a dashboard and its linked charts.

    Creates a top-down flowchart with the dashboard as the root node and
    each chart as a child node. Charts can be identified by ID or by info dicts
    containing 'slice_name' and 'id' keys.

    Args:
        dashboard_title: Dashboard name for the root node.
        chart_ids: Optional list of chart integer IDs (fallback if no chart_info).
        chart_info: Optional list of dicts, each with 'id' and 'slice_name' keys.

    Returns:
        Mermaid 'flowchart TD' diagram string with dashboard → chart edges.

        Example:
            >>> print(dashboard_to_mermaid("Sales Overview", chart_ids=[1, 2, 3]))
            flowchart TD
                DASH["Dashboard: Sales Overview"]
                C0["Chart 1"]
                DASH --> C0
                C1["Chart 2"]
                DASH --> C1
                C2["Chart 3"]
                DASH --> C2
            >>> print(dashboard_to_mermaid("KPIs", chart_info=[
            ...     {"id": 10, "slice_name": "Revenue KPI"},
            ...     {"id": 11, "slice_name": "Costs KPI"}]))
            flowchart TD
                DASH["Dashboard: KPIs"]
                C0["Revenue KPI"]
                DASH --> C0
                C1["Costs KPI"]
                DASH --> C1

        Note:
            Use in Markdown fenced code blocks with ```mermaid ... ``` to render.
    """
    chart_info = chart_info or []
    chart_ids = chart_ids or []
    # Step 2: If only IDs provided (no names), synthesize name dicts
    if not chart_info and chart_ids:
        chart_info = [{"id": cid, "slice_name": f"Chart {cid}"} for cid in chart_ids]
    # Step 3: Build the flowchart starting with the dashboard root node
    lines = [
        "flowchart TD",
        f'    DASH["Dashboard: {_sanitize(dashboard_title)}"]',
    ]
    # Step 4: Add each chart node and connect it to the dashboard root
    for i, info in enumerate(chart_info):
        cname = _sanitize(info.get("slice_name", f"Chart {info.get('id', i)}"))
        lines.append(f'    C{i}["{cname}"]')
        lines.append(f'    DASH --> C{i}')
    return "\n".join(lines)
