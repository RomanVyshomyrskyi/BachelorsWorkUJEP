"""
Chart-to-Mermaid diagram generation handlers.

Contains all per-chart-type handler functions and the dispatch table.
Each handler takes (title, metric, groupby, params) and returns a
Mermaid diagram syntax string.

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
"""
from typing import Any, Dict, List

from modules.SupersetModule.tools.mermaid.base import _extract_groupby, _extract_metric_name, _sanitize


# ── Per-Type Handler Functions ──


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
