import json
import uuid
from typing import List, Dict, Any, Optional

def generate_robust_dashboard_layout(chart_info: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generates a robust position_json for Superset.
    Enforces ROOT -> GRID -> ROW hierarchy.
    chart_info: List of dicts with {'id': int, 'name': str}
    """
    dashboard_uuid = str(uuid.uuid4())[:8]
    layout = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {
            "type": "ROOT",
            "id": "ROOT_ID",
            "children": ["GRID_ID"]
        },
        "GRID_ID": {
            "type": "GRID",
            "id": "GRID_ID",
            "children": [],
            "parents": ["ROOT_ID"]
        }
    }

    # Group charts into rows (max 2 charts per row for clear visibility)
    rows = [chart_info[i:i + 2] for i in range(0, len(chart_info), 2)]
    
    for row_idx, row_charts in enumerate(rows):
        row_id = f"ROW-R{row_idx}-{dashboard_uuid}"
        layout["GRID_ID"]["children"].append(row_id)
        
        layout[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": [],
            "parents": ["GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"}
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
                    "chartId": chart['id'],
                    "height": 50,
                    "width": 6,
                    "sliceName": chart['name']
                }
            }
            
    return layout

def get_standard_chart_params(viz_type: str, datasource_id: int, **kwargs) -> Dict[str, Any]:
    """
    Returns a standard set of parameters for common viz types.
    Reflects deviations for modern ECharts Superset instances.
    """
    # 1. Map generic types to modern ECharts equivalents
    type_map = {
        "line": "echarts_timeseries_line",
        "area": "echarts_timeseries_area",
        "bar": "echarts_bar",
        "dist_bar": "echarts_timeseries_bar",
        "big_number": "big_number",
        "scatter": "echarts_timeseries_scatter",
        "histogram": "echarts_timeseries_histogram",
        "waterfall": "echarts_timeseries_waterfall",
        "boxplot": "echarts_boxplot",
        "graph": "echarts_graph",
        "pie": "pie",
        "table": "table",
        "radar": "radar",
        "heatmap": "heatmap_v2",
        "treemap": "treemap_v2",
        "sankey": "sankey_v2",
        "sunburst": "sunburst_v2",
        "funnel": "funnel",
        "gauge": "gauge",
        "gantt": "gantt",
        "world_map": "world_map",
        "word_cloud": "word_cloud",
        "pivot_table": "pivot_table",
        "parallel": "parallel"
    }
    
    actual_viz_type = type_map.get(viz_type, viz_type)
    
    base = {
        "datasource": f"{datasource_id}__table",
        "viz_type": actual_viz_type,
        "adhoc_filters": [],
        "row_limit": 1000,
    }
    
    # 2. Add Area specific styling if requested
    if viz_type == "area":
        base["show_area"] = True
        base["stack"] = "Stack"

    # 3. Handle ECharts specific x_axis mapping vs legacy groupby
    if actual_viz_type.startswith("echarts_timeseries") or actual_viz_type == "echarts_area":
        if "x_axis" not in kwargs:
            # Heuristic: if 'groupby' was provided as a string or list, move first item to x_axis
            if "groupby" in kwargs:
                gb = kwargs["groupby"]
                if isinstance(gb, list) and len(gb) > 0:
                    base["x_axis"] = gb[0]
                elif isinstance(gb, str):
                    base["x_axis"] = gb
            else:
                base["x_axis"] = "year" # Reasonable default for provided WB data
        
        if "time_grain_sqla" not in kwargs:
            base["time_grain_sqla"] = "P1Y"

    # Merge overrides
    base.update(kwargs)
            
    return base

def get_chart_creation_rules() -> str:
    return """
# Superset Chart Creation Rules (Modern ECharts)

1. **Valid Viz Types**: Supported visualization types:
   - Bar: `echarts_bar` (category), `echarts_timeseries_bar` (time-based)
   - Line: `echarts_timeseries_line`
   - Area: `echarts_timeseries_area`
   - Scatter: `echarts_timeseries_scatter`
   - Pie: `pie`
   - Table: `table`
   - Big Number: `big_number`
   - And more: `radar`, `heatmap_v2`, `treemap_v2`, `sankey_v2`, `sunburst_v2`, `funnel`, `gauge`, `gantt`, `world_map`, `word_cloud`

2. **X-Axis Mapping**:
   - For time-series ECharts plugins, you MUST map the primary dimension (time or category) to the `x_axis` property.
   - Legacy `groupby` is used for series breaking, not the primary axis.

3. **Mandatory Time Fields**:
   - For any time-series chart, `time_grain_sqla` (e.g., 'P1Y', 'P1M') must be defined.

4. **Validation**: Always call `superset_get_standard_chart_params` to resolve generic names to correct plugin IDs and required keys.
"""

def get_dashboard_creation_rules() -> str:
    return """
# Superset Dashboard Creation Rules

1. **Strict Hierarchy**: Every `position_json` must follow: `ROOT` -> `GRID` -> `ROW` -> `CHART`.
   - Charts MUST be children of a `ROW`.
   - Rows MUST be children of the `GRID_ID`.

2. **Required Properties**:
   - Every component must have a `children` array (even if empty `[]`).
   - Every component must have a `parents` array.
   - Components should use standardized string IDs: `ROW-xxxx`, `CHART-xxxx`.

3. **Meta Data**:
   - `CHART` meta must include `chartId` (integer) and `sliceName` (string).
   - `width` should be between 1 and 12 (Superset uses a 12-column grid).

4. **Avoid Top-Level Charts**: Never place a `CHART` directly under `GRID_ID`. This causes 'length of undefined' errors in the Superset frontend.
"""
