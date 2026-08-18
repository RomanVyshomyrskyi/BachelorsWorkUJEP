"""
Superset chart to Mermaid.js diagram conversion utilities.

Converts Superset chart configurations into Mermaid.js diagram syntax
for visualizing chart structure, data flow, and dashboard layout as
text-based diagrams that render in Markdown-compatible viewers.

Chart-to-Diagram Dispatcher:
    The `_DISPATCH` dictionary maps each Superset viz_type to a dedicated
    Mermaid generator function. The mapping follows these visual semantics:

    - **pie** → Pie chart ("pie title ...")
    - **echarts_timeseries_line** → XY chart with line series ("xychart-beta")
    - **echarts_timeseries_bar** → XY chart with bar series
    - **echarts_area** → XY chart (area rendered as line for simplicity)
    - **echarts_timeseries_scatter** → XY chart
    - **bubble_v2** → XY chart
    - **mixed_timeseries** → XY chart
    - **histogram_v2** → XY chart with bar series
    - **box_plot** → XY chart with bar series
    - **big_number / big_number_total / gauge_chart** → Flowchart card ("flowchart LR")
    - **funnel** → Flowchart steps ("flowchart TD")
    - **gantt_chart** → Gantt diagram ("gantt")
    - **sunburst_v2 / treemap_v2 / tree_chart** → Mindmap ("mindmap")
    - **graph_chart** → Flowchart network ("flowchart LR")
    - **table / word_cloud / world_map / pivot_table_v2 / heatmap_v2 /
      sankey_v2 / radar / parallel / waterfall** → Config card (fallback)

    Unknown viz_type defaults to the config card showing chart metadata.

Dashboard Layout:
    `dashboard_to_mermaid()` renders a flowchart showing the dashboard title
    connected to each chart node, providing a quick visual overview of the
    dashboard structure.

Usage:
    >>> chart_to_mermaid("pie", {"metric": "count"}, "Sales Pie")
    >>> dashboard_to_mermaid("My Dashboard", [1, 2, 3])
"""
from typing import Any, Dict, Optional

from modules.SupersetModule.tools.mermaid.base import (
    _extract_groupby,
    _extract_metric_name,
)
from modules.SupersetModule.tools.mermaid.charts import (
    _mermaid_big_number,
    _mermaid_config_card,
    _mermaid_funnel,
    _mermaid_gantt,
    _mermaid_graph_network,
    _mermaid_mindmap,
    _mermaid_pie,
    _mermaid_xy,
)
from modules.SupersetModule.tools.mermaid.dashboards import dashboard_to_mermaid

# ── Viz Type to Mermaid Generator Dispatch Table ──
#   Maps each Superset viz_type to a function that generates the appropriate
#   Mermaid diagram. Lambda wrappers pass the 'series' parameter for bar charts.
_DISPATCH: Dict[str, Any] = {
    # Circular / part-to-whole
    "pie": _mermaid_pie,
    # Time series → XY chart (line variant)
    "echarts_timeseries_line": _mermaid_xy,
    "echarts_area": _mermaid_xy,
    "echarts_timeseries_scatter": _mermaid_xy,
    "bubble_v2": _mermaid_xy,
    "mixed_timeseries": _mermaid_xy,
    # Time series → XY chart (bar variant via lambda)
    "echarts_timeseries_bar": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    # Statistical → XY chart (bar variant)
    "histogram_v2": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    "box_plot": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    # Single value → flowchart card
    "big_number": _mermaid_big_number,
    "big_number_total": _mermaid_big_number,
    "gauge_chart": _mermaid_big_number,
    # Flow / process → flowchart (TD) or gantt
    "gantt_chart": _mermaid_gantt,
    "funnel": _mermaid_funnel,
    # Hierarchical → mindmap
    "sunburst_v2": _mermaid_mindmap,
    "treemap_v2": _mermaid_mindmap,
    "tree_chart": _mermaid_mindmap,
    # Network → flowchart
    "graph_chart": _mermaid_graph_network,
    # Tabular / geospatial / misc → config card (fallback display)
    "table": _mermaid_config_card,
    "word_cloud": _mermaid_config_card,
    "world_map": _mermaid_config_card,
    "pivot_table_v2": _mermaid_config_card,
    "heatmap_v2": _mermaid_config_card,
    "sankey_v2": _mermaid_config_card,
    "radar": _mermaid_config_card,
    "parallel": _mermaid_config_card,
    "waterfall": _mermaid_config_card,
}


def chart_to_mermaid(
    viz_type: str,
    params: Optional[Dict[str, Any]] = None,
    chart_name: str = "Chart",
) -> str:
    """Convert a single Superset chart config into a Mermaid.js diagram.

    Looks up the viz_type in the dispatch table and delegates to the
    appropriate generator function. Unknown viz_types fall back to the
    config card display.

    Args:
        viz_type: Superset viz_type string (e.g. "pie", "echarts_timeseries_line").
        params: Optional chart params dict with metric/groupby/viz_type keys.
        chart_name: Human-readable chart name for the diagram title.

    Returns:
        Mermaid diagram string suitable for rendering in Markdown.

        Examples:
            >>> print(chart_to_mermaid("pie", {"metric": "count", "groupby": ["product_line"]}, "Sales Pie"))
            pie title "Sales Pie"
                "product_line" : 30
            >>> print(chart_to_mermaid("echarts_timeseries_line", {}, "Revenue Trend"))
            xychart-beta
                title "Revenue Trend"
                x-axis "Category" [...]
                y-axis "?" 0 --> 100
                line [...]

        Note:
            Use in Markdown fenced code blocks with ```mermaid ... ``` to render.
    """
    # Step 1: Extract metric name and groupby columns for diagram generation
    metric = _extract_metric_name(params or {})
    groupby = _extract_groupby(params or {})
    # Step 2: Look up the handler — fallback to config card for unknown types
    handler = _DISPATCH.get(viz_type, _mermaid_config_card)
    # Step 3: Invoke the handler to produce the Mermaid diagram string
    return handler(chart_name, metric, groupby, params or {})


__all__ = [
    "chart_to_mermaid",
    "dashboard_to_mermaid",
    "_DISPATCH",
]
