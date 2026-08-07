"""
Chart parameter generation strategies for Apache Superset visualizations.

Implements the Strategy Pattern with a base class and 26+ concrete strategies,
one per chart/viz type. Each strategy knows how to build a fully-formed
params dict conforming to Superset's chart API requirements for its viz type.

Usage:
    params = get_standard_chart_params("line", 13, x_axis="order_date", metrics=["SUM(sales)"])
    # Returns properly structured params dict with datasource, viz_type, metrics, etc.

Architecture:
    TYPE_MAP      – maps user-friendly viz_type aliases (e.g. "line") to actual Superset viz_type (e.g. "echarts_timeseries_line")
    _REGISTRY     – maps actual viz_type strings to instantiated strategy objects
    get_standard_chart_params() – public API: resolves viz_type → strategy → build()
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy
from . import timeseries, scatter_bubble, categorical, hierarchy, spatial, kpi, display, tables, analytics


# ─────────────────────────────────────────────────────────────────────────────
#  Registry –  maps generic / actual viz_type → strategy class
# ─────────────────────────────────────────────────────────────────────────────

# TYPE_MAP: maps user-friendly chart type names (aliases) to actual Superset
# viz_type strings registered by chart plugins. This allows users to pass
# simplified names like "line" or "bar" and have them resolved automatically.
TYPE_MAP: Dict[str, str] = {
    "line": "echarts_timeseries_line",
    "bar": "echarts_timeseries_bar",
    "dist_bar": "echarts_timeseries_bar",
    "area": "echarts_area",
    "scatter": "echarts_timeseries_scatter",
    "bubble": "bubble_v2",
    "pie": "pie",
    "table": "table",
    "big_number": "big_number",
    "big_number_total": "big_number_total",
    "gauge": "gauge_chart",
    "gantt": "gantt_chart",
    "box_plot": "box_plot",
    "boxplot": "box_plot",
    "funnel": "funnel",
    "graph": "graph_chart",
    "waterfall": "waterfall",
    "heatmap": "heatmap_v2",
    "histogram": "histogram_v2",
    "radar": "radar",
    "sankey": "sankey_v2",
    "sunburst": "sunburst_v2",
    "treemap": "treemap_v2",
    "tree": "tree_chart",
    "pivot_table": "pivot_table_v2",
    "mixed_timeseries": "mixed_timeseries",
    "word_cloud": "word_cloud",
    "world_map": "world_map",
    "map": "world_map",
}

# _REGISTRY: maps actual Superset viz_type strings to instantiated strategy objects.
_REGISTRY: Dict[str, ChartParamsStrategy] = {
    "echarts_timeseries_line": timeseries.LineChartStrategy(),
    "echarts_timeseries_bar": timeseries.BarChartStrategy(),
    "echarts_area": timeseries.AreaChartStrategy(),
    "echarts_timeseries_scatter": scatter_bubble.ScatterChartStrategy(),
    "bubble_v2": scatter_bubble.BubbleChartStrategy(),
    "pie": categorical.PieChartStrategy(),
    "table": tables.TableChartStrategy(),
    "big_number": kpi.BigNumberChartStrategy(),
    "big_number_total": kpi.BigNumberTotalStrategy(),
    "gauge_chart": kpi.GaugeChartStrategy(),
    "gantt_chart": display.GanttChartStrategy(),
    "box_plot": display.BoxPlotStrategy(),
    "funnel": categorical.FunnelStrategy(),
    "graph_chart": display.GraphChartStrategy(),
    "waterfall": categorical.WaterfallStrategy(),
    "heatmap_v2": display.HeatmapStrategy(),
    "histogram_v2": display.HistogramStrategy(),
    "radar": analytics.RadarStrategy(),
    "sankey_v2": hierarchy.SankeyStrategy(),
    "sunburst_v2": hierarchy.SunburstStrategy(),
    "treemap_v2": hierarchy.TreeMapStrategy(),
    "tree_chart": hierarchy.TreeStrategy(),
    "pivot_table_v2": tables.PivotTableStrategy(),
    "mixed_timeseries": scatter_bubble.MixedTimeseriesStrategy(),
    "word_cloud": analytics.WordCloudStrategy(),
    "world_map": spatial.WorldMapStrategy(),
}


# ─────────────────────────────────────────────────────────────────────────────
#  Public API –  backwards compatible wrapper
# ─────────────────────────────────────────────────────────────────────────────


def get_standard_chart_params(viz_type: str, datasource_id: int, **kwargs) -> Dict[str, Any]:
    """
    Generate chart params using the strategy for the requested viz_type.

    Description:
        Public API function that resolves a user-friendly chart type name to the
        actual Superset viz_type, looks up the corresponding strategy from the
        registry, and calls its build() method. Falls back to minimal params
        for unknown chart types.

    Args:
        viz_type: Chart type identifier. Accepts user-friendly names like "line",
                  "bar", "pie", etc. (resolved via TYPE_MAP) or actual Superset
                  viz_type strings like "echarts_timeseries_line".
        datasource_id: The Superset datasource/table ID to query (e.g. 13).
        **kwargs: Optional parameter overrides passed through to the strategy's build() method.
                  Common kwargs: metrics, groupby, x_axis, time_grain_sqla, metric, etc.

    Returns:
        A fully-formed params dict ready to be JSON-serialized and sent to Superset's
        chart creation API. Contains keys like 'datasource', 'viz_type', 'metrics',
        'groupby', 'adhoc_filters', 'row_limit', and chart-type-specific fields.

    Example:
        >>> params = get_standard_chart_params("line", 13,
        ...     x_axis="order_date",
        ...     time_grain_sqla="P1M",
        ...     metrics=["SUM(sales)"],
        ...     groupby=["product_line"])
        >>> params["viz_type"]
        'echarts_timeseries_line'
        >>> params["datasource"]
        '13__table'

        # For JSON serialization:
        >>> import json
        >>> params_json = json.dumps(params)
    """
    actual_viz = TYPE_MAP.get(viz_type, viz_type)
    strategy = _REGISTRY.get(actual_viz)
    if strategy is None:
        return {
            "datasource": f"{datasource_id}__table",
            "viz_type": actual_viz,
            "adhoc_filters": [],
            "row_limit": kwargs.get("row_limit", 10000),
            "metric": kwargs.get("metric", "count"),
            "metrics": kwargs.get("metrics", ["count"]),
            "groupby": kwargs.get("groupby", []),
        }
    return strategy.build(datasource_id, **kwargs)
