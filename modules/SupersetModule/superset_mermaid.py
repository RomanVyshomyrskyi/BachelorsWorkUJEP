import json
from typing import Any, Dict, List, Optional


def _extract_metric_name(params: Dict[str, Any]) -> str:
    metric = params.get("metric") or (params.get("metrics") or [None])[0]
    if isinstance(metric, dict):
        agg = metric.get("aggregate", "?")
        col = metric.get("column", {}).get("column_name", "?")
        return f"{agg}({col})"
    return str(metric) if metric else "?"


def _extract_groupby(params: Dict[str, Any]) -> List[str]:
    groupby = params.get("groupby", [])
    return list(groupby) if isinstance(groupby, list) else []


def _sanitize(val: str) -> str:
    return val.replace('"', "'").replace("<br/>", " ")


def _mermaid_pie(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    labels = groupby or ["Category A", "Category B", "Category C", "Category D"]
    lines = [f'pie title "{_sanitize(title)}"']
    values = [30, 25, 20, 15, 10]
    for i, label in enumerate(labels):
        v = values[i % len(values)]
        lines.append(f'    "{_sanitize(label)}" : {v}')
    return "\n".join(lines)


def _mermaid_xy(title: str, metric: str, groupby: List[str], params: Dict[str, Any], series: str = "line") -> str:
    x_axis = groupby or ["Jan", "Feb", "Mar", "Apr", "May", "Jun"]
    x_label = params.get("x_axis_label", groupby[0] if groupby else "Category")
    values = [30, 55, 42, 78, 61, 90]
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
    val = params.get("metric", {}).get("label", "1,234,567") if isinstance(params.get("metric"), dict) else "1,234,567"
    lines = [
        "flowchart LR",
        f'    Metric["{_sanitize(title)}<br/>{_sanitize(str(val))}<br/>Metric: {_sanitize(metric)}"]',
    ]
    return "\n".join(lines)


def _mermaid_funnel(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    stages = groupby or ["Visitors", "Leads", "Opportunities", "Customers"]
    values = [10000, 2500, 750, 200]
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
    tasks = groupby or ["Requirement Analysis", "Design", "Development", "Testing", "Deployment"]
    lines = [
        "gantt",
        f'    title {_sanitize(title)}',
        "    dateFormat YYYY-MM-DD",
        f'    section {_sanitize(metric)}',
    ]
    for i, task in enumerate(tasks):
        start_days = i * 20 + 1
        dur = 15 + (i * 5)
        lines.append(f'    {_sanitize(task)} :a{i}, 2024-01-{start_days:02d}, {dur}d')
    return "\n".join(lines)


def _mermaid_mindmap(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    children = groupby or ["Category A", "Category B", "Category C"]
    lines = ["mindmap", f'  root(({_sanitize(title)}))']
    for child in children:
        lines.append(f'    {_sanitize(child)}')
    lines.append(f'    Metric: {_sanitize(metric)}')
    return "\n".join(lines)


def _mermaid_graph_network(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    nodes = groupby or ["Node A", "Node B", "Node C", "Node D"]
    lines = ["flowchart LR"]
    for i, node in enumerate(nodes):
        lines.append(f'    N{i}["{_sanitize(node)}"]')
    for i in range(len(nodes) - 1):
        lines.append(f'    N{i} --> N{i + 1}')
    return "\n".join(lines)


def _mermaid_config_card(title: str, metric: str, groupby: List[str], params: Dict[str, Any]) -> str:
    viz = params.get("viz_type", "?")
    lines = [
        "flowchart LR",
        f'    Title["<b>{_sanitize(title)}</b>"]',
        f'    Viz["Viz Type: {_sanitize(viz)}"]',
        f'    Metric["Metric: {_sanitize(metric)}"]',
    ]
    if groupby:
        gb = ", ".join(_sanitize(g) for g in groupby)
        lines.append(f'    GroupBy["Group By: {gb}"]')
    lines.append("    Title --> Viz")
    lines.append("    Viz --> Metric")
    if groupby:
        lines.append("    Metric --> GroupBy")
    return "\n".join(lines)


_DISPATCH: Dict[str, Any] = {
    "pie": _mermaid_pie,
    "echarts_timeseries_line": _mermaid_xy,
    "echarts_timeseries_bar": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    "echarts_area": _mermaid_xy,
    "echarts_timeseries_scatter": _mermaid_xy,
    "bubble_v2": _mermaid_xy,
    "big_number": _mermaid_big_number,
    "big_number_total": _mermaid_big_number,
    "gauge_chart": _mermaid_big_number,
    "mixed_timeseries": _mermaid_xy,
    "histogram_v2": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    "box_plot": lambda t, m, g, p: _mermaid_xy(t, m, g, p, "bar"),
    "gantt_chart": _mermaid_gantt,
    "funnel": _mermaid_funnel,
    "sunburst_v2": _mermaid_mindmap,
    "treemap_v2": _mermaid_mindmap,
    "tree_chart": _mermaid_mindmap,
    "graph_chart": _mermaid_graph_network,
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
    params = params or {}
    vt = viz_type.lower().replace(" ", "_")
    metric = _extract_metric_name(params)
    groupby = _extract_groupby(params)
    handler = _DISPATCH.get(vt, _mermaid_config_card)
    return handler(chart_name, metric, groupby, params)


def dashboard_to_mermaid(
    dashboard_title: str,
    chart_ids: Optional[List[int]] = None,
    chart_info: Optional[List[Dict[str, Any]]] = None,
) -> str:
    lines = ["flowchart TD", f'    DASH["Dashboard: {_sanitize(dashboard_title)}"]']
    chart_info = chart_info or []
    chart_ids = chart_ids or []
    if not chart_info and chart_ids:
        chart_info = [{"id": cid, "slice_name": f"Chart {cid}"} for cid in chart_ids]
    for i, info in enumerate(chart_info):
        cname = _sanitize(info.get("slice_name", f"Chart {info.get('id', i)}"))
        lines.append(f'    C{i}["{cname}"]')
        lines.append(f'    DASH --> C{i}')
    return "\n".join(lines)
