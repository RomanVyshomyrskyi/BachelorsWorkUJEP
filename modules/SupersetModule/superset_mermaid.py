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

import json
from typing import Any, Dict, List, Optional


def _extract_metric_name(params: Dict[str, Any]) -> str:
    """Extract a human-readable metric name from chart params for diagram display.

    Tries the singular 'metric' field first, then the first element of the
    'metrics' array. For AdHocMetricObject dicts, formats as 'AGG(col_name)'.
    For strings, returns as-is. Falls back to '?' if no metric found.

    Args:
        params: Chart params dict potentially containing 'metric' or 'metrics'.

    Returns:
        A string like "SUM(sales)", "count", or "?".
    """
    # Step 1: Try singular 'metric' first, then first element of 'metrics' array
    metric = params.get("metric") or (params.get("metrics") or [None])[0]
    # Step 2: If it's an AdHocMetricObject dict, format as aggregate(column_name)
    if isinstance(metric, dict):
        agg = metric.get("aggregate", "?")
        col = metric.get("column", {}).get("column_name", "?")
        return f"{agg}({col})"
    # Step 3: String metrics returned as-is, None becomes '?'
    return str(metric) if metric else "?"


def _extract_groupby(params: Dict[str, Any]) -> List[str]:
    """Extract groupby column names from chart params for diagram axis labels.

    Args:
        params: Chart params dict potentially containing 'groupby' as list.

    Returns:
        List of groupby column name strings, or empty list if not found.
    """
    # Step 1: Get the groupby value — should be a list of column names
    groupby = params.get("groupby", [])
    # Step 2: Ensure it's a list (defensive against string groupby)
    return list(groupby) if isinstance(groupby, list) else []


def _sanitize(val: str) -> str:
    """Sanitize a string for safe embedding in Mermaid diagram syntax.

    Replaces characters that would break Mermaid rendering:
    - Double quotes → single quotes (Mermaid uses double quotes as delimiters)
    - <br/> → space (newline markers don't render in diagram labels)

    Args:
        val: Raw string to sanitize.

    Returns:
        Mermaid-safe string with problematic characters replaced.
    """
    # Step 1: Replace double quotes with single quotes to avoid breaking Mermaid syntax
    # Step 2: Replace HTML <br/> tags with spaces (they have no meaning in diagrams)
    return val.replace('"', "'").replace("<br/>", " ")


def _mermaid_pie(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid pie chart diagram from chart params.

    Uses groupby columns as slice labels or falls back to generic categories.
    Values are placeholders since actual data isn't available at config time.

    Args:
        title: Chart title for the diagram heading.
        metric: Metric name for display context.
        groupby: Category labels for pie slices.
        params: Full chart params dict (unused, kept for dispatcher consistency).

    Returns:
        Mermaid 'pie' diagram syntax string.
    """
    # Step 1: Determine labels — use groupby columns or default categories
    labels = groupby or ["Category A", "Category B", "Category C", "Category D"]
    # Step 2: Start the pie diagram with sanitized title
    lines = [f'pie title "{_sanitize(title)}"']
    # Step 3: Assign placeholder values cycled through a fixed list
    values = [30, 25, 20, 15, 10]
    for i, label in enumerate(labels):
        v = values[i % len(values)]
        lines.append(f'    "{_sanitize(label)}" : {v}')
    return "\n".join(lines)


def _mermaid_xy(title: str, metric: str, groupby: List[str], params: Dict[str, Any], series: str = "line") -> str:
    """Generate a Mermaid xychart-beta diagram (line, bar, area, scatter).

    Uses groupby columns as x-axis labels with placeholder y-values.
    The series parameter controls the chart type rendering (line/bar).

    Args:
        title: Chart title for the diagram heading.
        metric: Metric name shown on the y-axis.
        groupby: X-axis label list.
        params: Full chart params dict (unused, kept for dispatcher consistency).
        series: Mermaid series type — "line" or "bar".

    Returns:
        Mermaid 'xychart-beta' diagram syntax string.
    """
    # Step 1: Determine x-axis labels — groupby columns or default month labels
    x_axis = groupby or ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    x_label = params.get("x_axis_label", groupby[0] if groupby else "Category")
    # Step 2: Generate placeholder y-values aligned with the number of x labels
    values = [30, 55, 42, 78, 61, 90]
    # Step 3: Build the xychart-beta diagram with sanitized labels and data
    x_items = ", ".join(f'"{_sanitize(x)}"' for x in x_axis)
    data = ", ".join(str(v) for v in values[:len(x_axis)])
    lines = [
        "xychart-beta",
        f'    title "{_sanitize(title)}"',
        f'    x-axis "{_sanitize(x_label)}" [{x_items}]',
        f'    y-axis "{_sanitize(metric)}" 0 --> 100',
        f'    {series} [{data}]',
    ]
    return "\n".join(lines)


def _mermaid_big_number(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid flowchart card for big number / gauge charts.

    Shows the metric label (or placeholder value) in a single flowchart node,
    rendering as a callout card in Mermaid viewers.

    Args:
        title: Chart title for the node display.
        metric: Metric name shown in the card.
        groupby: Groupby list (unused in big number visualization).
        params: Chart params — the 'metric' key's 'label' is extracted for display.

    Returns:
        Mermaid 'flowchart LR' diagram string with a single metric card node.
    """
    # Step 1: Extract the metric label from an AdHocMetricObject or use a placeholder
    val = params.get("metric", {}).get("label", "1,234,567") if isinstance(params.get("metric"), dict) else "1,234,567"
    # Step 2: Build a single flowchart node with title, value, and metric name
    lines = [
        "flowchart LR",
        f'    Metric["{_sanitize(title)}<br/>{_sanitize(str(val))}<br/>Metric: {_sanitize(metric)}"]',
    ]
    return "\n".join(lines)


def _mermaid_funnel(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid flowchart diagram representing a funnel.

    Stages are taken from groupby columns (or default funnel steps).
    Connected vertically with arrows to show the funnel progression.

    Args:
        title: Funnel title for context (embedded in first node implicitly).
        metric: Metric name shown in each stage.
        groupby: Funnel stage names; defaults to generic marketing funnel stages.
        params: Full chart params (unused).

    Returns:
        Mermaid 'flowchart TD' diagram string with vertically linked nodes.
    """
    # Step 1: Determine stage names — groupby columns or default funnel stages
    stages = groupby or ["Visitors", "Leads", "Opportunities", "Customers"]
    # Step 2: Assign placeholder values proportional to stage depth
    values = [10000, 2500, 750, 200]
    # Step 3: Build flowchart nodes connected top-to-bottom with arrows
    lines = ["flowchart TD"]
    prev = None
    for i, (stage, val) in enumerate(zip(stages, values[:len(stages)])):
        node = f"S{i}"
        display = f"{stage}: {val:,}"
        lines.append(f'    {node}["{_sanitize(display)}"]')
        if prev:
            lines.append(f'    {prev} --> {node}')
        prev = node
    return "\n".join(lines)


def _mermaid_gantt(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid gantt diagram from chart params.

    Uses groupby columns as task names with computed start dates and durations
    for a staggered project timeline visualization.

    Args:
        title: Gantt chart title.
        metric: Metric name used as the gantt section label.
        groupby: Task names; defaults to a software development lifecycle.
        params: Full chart params (unused).

    Returns:
        Mermaid 'gantt' diagram syntax string.
    """
    # Step 1: Determine task names — groupby columns or default SDLC tasks
    tasks = groupby or ["Requirement Analysis", "Design", "Development", "Testing", "Deployment"]
    # Step 2: Build gantt diagram header with date format and section
    lines = [
        "gantt",
        f'    title {_sanitize(title)}',
        "    dateFormat YYYY-MM-DD",
        f'    section {_sanitize(metric)}',
    ]
    # Step 3: Create staggered tasks — each starts after the previous, with increasing duration
    for i, task in enumerate(tasks):
        start_days = i * 20 + 1
        dur = 15 + (i * 5)
        lines.append(f'    {_sanitize(task)} :a{i}, 2024-01-{start_days:02d}, {dur}d')
    return "\n".join(lines)


def _mermaid_mindmap(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid mindmap for hierarchical chart types (sunburst, treemap, tree).

    Renders groupby columns as first-level children under a root node,
    with the metric appended as a leaf node.

    Args:
        title: Chart title — used as the mindmap root label.
        metric: Metric name for the leaf node.
        groupby: Hierarchy level labels as first-level children.
        params: Full chart params (unused).

    Returns:
        Mermaid 'mindmap' diagram syntax string.
    """
    # Step 1: Determine child labels — groupby columns or default categories
    children = groupby or ["Category A", "Category B", "Category C"]
    # Step 2: Build mindmap starting from root node with title
    lines = ["mindmap", f'  root(({_sanitize(title)}))']
    # Step 3: Add first-level children, then metric as an additional leaf
    for child in children:
        lines.append(f'    {_sanitize(child)}')
    lines.append(f'    Metric: {_sanitize(metric)}')
    return "\n".join(lines)


def _mermaid_graph_network(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid flowchart network for graph_chart.

    Creates a linear chain of nodes (from groupby columns) connected left-to-right.
    Represents a simplified directed graph structure.

    Args:
        title: Graph title (embedded in node names).
        metric: Metric name for display context.
        groupby: Node names for the graph.
        params: Full chart params (unused).

    Returns:
        Mermaid 'flowchart LR' diagram string with linearly linked nodes.
    """
    # Step 1: Determine node labels — groupby columns or default node names
    nodes = groupby or ["Node A", "Node B", "Node C", "Node D"]
    # Step 2: Build flowchart nodes, then connect them in a chain
    lines = ["flowchart LR"]
    for i, node in enumerate(nodes):
        lines.append(f'    N{i}["{_sanitize(node)}"]')
    for i in range(len(nodes) - 1):
        lines.append(f'    N{i} --> N{i + 1}')
    return "\n".join(lines)


def _mermaid_config_card(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    """Generate a Mermaid config card as fallback for chart types without dedicated diagrams.

    Shows chart metadata (viz_type, metric, groupby) in flowchart nodes connected
    left-to-right. Provides a consistent representation for any unsupported viz_type.

    Args:
        title: Chart title for the card heading.
        metric: Metric name shown in the metric node.
        groupby: Groupby columns shown in an optional GroupBy node.
        params: Chart params dict — 'viz_type' is extracted for display.

    Returns:
        Mermaid 'flowchart LR' diagram string with config metadata nodes.
    """
    # Step 1: Extract viz_type from params for the config display
    viz = params.get("viz_type", "?")
    # Step 2: Build metadata nodes: Title, Viz Type, Metric
    lines = [
        "flowchart LR",
        f'    Title["<b>{_sanitize(title)}</b>"]',
        f'    Viz["Viz Type: {_sanitize(viz)}"]',
        f'    Metric["Metric: {_sanitize(metric)}"]',
    ]
    # Step 3: Optionally add a GroupBy node if groupby columns exist
    if groupby:
        gb = ", ".join(_sanitize(g) for g in groupby)
        lines.append(f'    GroupBy["Group By: {gb}"]')
    # Step 4: Connect nodes left-to-right in a metadata chain
    lines.append("    Title --> Viz")
    lines.append("    Viz --> Metric")
    if groupby:
        lines.append("    Metric --> GroupBy")
    return "\n".join(lines)


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

        Example:
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
    # Step 2: Extract metric name and groupby columns for diagram generation
    metric = _extract_metric_name(params)
    groupby = _extract_groupby(params)
    # Step 3: Look up the handler — fallback to config card for unknown types
    handler = _DISPATCH.get(vt, _mermaid_config_card)
    # Step 4: Invoke the handler to produce the Mermaid diagram string
    return handler(chart_name, metric, groupby, params)


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
    # Step 3: Add each chart node and connect it to the dashboard root
    for i, info in enumerate(chart_info):
        cname = _sanitize(info.get("slice_name", f"Chart {info.get('id', i)}"))
        lines.append(f'    C{i}["{cname}"]')
        lines.append(f'    DASH --> C{i}')
    return "\n".join(lines)
