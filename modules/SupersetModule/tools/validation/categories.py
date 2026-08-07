"""
Viz type category sets for Superset chart parameter validation.

These category sets classify every Superset chart viz_type by the
metric format it expects. Used by validate_chart_params to check format
correctness and by auto_fix_chart_params to apply the right conversions.

Aligned with Superset Dashboard Designer and SQL Developer skills:
- Metric format matches Superset API expectations
- Required field validation covers all registered chart types
- Temporal validation covers time_grain_sqla values
"""

from typing import Any, Dict

# ── Metric format categories ────────────────────────────────────────────────

# Category 1: Chart types that expect a SINGLE STRING metric.
#   "metric": "count"  or  "metric": "SUM(sales)"
#   Superset converts these to AdHocMetricObject with expressionType='SIMPLE'
SINGULAR_STRING_METRIC_TYPES: set = {
    "big_number",
    "big_number_total",
    "funnel",
    "gauge_chart",
    "graph_chart",
    "heatmap_v2",
    "sankey_v2",
    "sunburst_v2",
    "treemap_v2",
    "tree_chart",
    "word_cloud",
    "world_map",
}

# Category 2: Chart types that expect a SINGLE AdHocMetricObject dict.
#   "metric": {"aggregate": "SUM", "column": {"column_name": "..."}, "expressionType": "SIMPLE"}
SINGULAR_ADHOC_METRIC_TYPES: set = {
    "pie",
    "waterfall",
}

# Category 3: Chart types that expect an ARRAY of string metrics.
#   "metrics": ["count", "SUM(col)"]
#   Superset converts each to AdHocMetricObject on submission
STRING_METRICS_ARRAY_TYPES: set = {
    "echarts_timeseries_line",
    "echarts_timeseries_bar",
    "echarts_area",
    "echarts_timeseries_scatter",
    "bubble_v2",
    "box_plot",
}

# Category 4: Chart types that expect an ARRAY of AdHocMetricObject dicts.
#   "metrics": [{"aggregate": "SUM", "column": {...}, "expressionType": "SIMPLE"}]
ADHOC_METRICS_ARRAY_TYPES: set = {
    "mixed_timeseries",
    "pivot_table_v2",
}

# Category 5: Chart types that accept BOTH strings and objects in the metrics array.
MIXED_METRICS_TYPES: set = {
    "radar",
}

# Category 6: Chart types that have NO metric/metrics field at all.
#   Table uses all_columns + query_mode, not metrics
NO_METRICS_TYPES: set = {
    "histogram_v2",
    "gantt_chart",
    "table",
}

# ── Field requirement categories ────────────────────────────────────────────

# Category 7: Requires an 'entity' field for geographic mapping.
ENTITY_REQUIRED_TYPES: set = {
    "world_map",
}

# Category 8: Requires source/target fields and validates DAG structure.
SANKEY_TYPES: set = {
    "sankey_v2",
}

# Category 9: All chart types with their Superset API field requirements.
#   Maps viz_type -> {required, optional, x_axis_temporal, description}
#   Used for pre-submission validation before sending to Superset API
DATASOURCE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "world_map": {
        "required": ["entity"],
        "optional": ["groupby"],
        "metric_field": "metric",
        "description": "world_map needs entity field (geographic identifier like country_code, zipcode)",
    },
    "bubble_v2": {
        "required": ["x", "y", "size"],
        "optional": ["series", "entity"],
        "metric_field": "metrics",
        "description": "bubble_v2 needs x, y, and size as AdHocDimensionObject dicts with column.column_name",
    },
    "heatmap_v2": {
        "required": ["x_axis", "groupby"],
        "optional": [],
        "metric_field": "metric",
        "description": "heatmap_v2 needs x_axis and groupby (row dimension)",
    },
    "sunburst_v2": {
        "required": ["columns"],
        "optional": ["metric"],
        "metric_field": "metric",
        "description": "sunburst_v2 needs columns field (array of hierarchy levels)",
    },
    "treemap_v2": {
        "required": [],
        "optional": ["groupby"],
        "metric_field": "metric",
        "description": "treemap_v2 works with groupby or columns for hierarchy",
    },
    "radar": {
        "required": ["groupby"],
        "optional": ["metrics"],
        "metric_field": "metrics",
        "description": "radar needs groupby for dimension labels",
    },
    "box_plot": {
        "required": ["groupby"],
        "optional": ["metric"],
        "metric_field": "metrics",
        "description": "box_plot needs groupby for categories",
    },
    "histogram_v2": {
        "required": ["x_axis"],
        "optional": [],
        "description": "histogram_v2 needs x_axis for the value to bin",
    },
    "waterfall": {
        "required": ["groupby"],
        "optional": [],
        "metric_field": "metric",
        "description": "waterfall needs groupby for categories",
    },
    "funnel": {
        "required": ["groupby"],
        "optional": [],
        "metric_field": "metric",
        "description": "funnel needs groupby for steps",
    },
    "gauge_chart": {
        "required": [],
        "optional": ["groupby"],
        "metric_field": "metric",
        "description": "gauge_chart is flexible, works with count or custom metric",
    },
    "echarts_timeseries_line": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "time_grain_required": True,
        "metric_field": "metrics",
        "description": "time series needs temporal x_axis and time_grain_sqla (e.g., P1D, P1M, P1Y)",
    },
    "echarts_timeseries_bar": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "time_grain_required": True,
        "metric_field": "metrics",
        "description": "time series bar needs temporal x_axis and time_grain_sqla",
    },
    "echarts_area": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "time_grain_required": True,
        "metric_field": "metrics",
        "description": "area chart needs temporal x_axis and time_grain_sqla",
    },
    "echarts_timeseries_scatter": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "metric_field": "metrics",
        "description": "scatter chart needs temporal x_axis",
    },
    "big_number": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal_for_trendline": True,
        "metric_field": "metric",
        "description": "big_number with trendline needs temporal x_axis",
    },
    "big_number_total": {
        "required": [],
        "optional": ["groupby"],
        "metric_field": "metric",
        "description": "big_number_total shows aggregate without time dimension",
    },
    "table": {
        "required": ["query_mode", "all_columns"],
        "optional": ["groupby", "order_by_cols"],
        "description": "table chart needs query_mode='raw' and all_columns list",
    },
    "tree_chart": {
        "required": ["id", "parent", "name"],
        "optional": ["metric"],
        "metric_field": "metric",
        "description": "tree chart needs id, parent, and name columns for hierarchy",
    },
    "word_cloud": {
        "required": ["series"],
        "optional": ["metric"],
        "metric_field": "metric",
        "description": "word_cloud needs series column (text labels) and metric (size values)",
    },
    "mixed_timeseries": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "time_grain_required": True,
        "metric_field": "metrics",
        "description": "mixed timeseries needs temporal x_axis and AdHocMetricObject metrics",
    },
    "gantt_chart": {
        "required": ["start_time", "end_time"],
        "optional": [],
        "description": "gantt chart needs start_time and end_time temporal columns",
    },
    "pie": {
        "required": ["groupby"],
        "optional": [],
        "metric_field": "metric",
        "description": "pie chart needs groupby for slice categories and metric for slice sizes",
    },
    "graph_chart": {
        "required": ["node", "relationship"],
        "optional": ["metric"],
        "metric_field": "metric",
        "description": "graph chart needs node and relationship columns for network visualization",
    },
    "pivot_table_v2": {
        "required": ["groupbyColumns", "groupbyRows"],
        "optional": ["metrics"],
        "metric_field": "metrics",
        "description": "pivot table needs groupbyColumns and groupbyRows arrays",
    },
    "sankey_v2": {
        "required": ["source", "target"],
        "optional": ["metric"],
        "metric_field": "metric",
        "description": "sankey needs source and target columns for flow visualization",
    },
}

# Category 10: Chart types that need time_grain_sqla.
#   All time-based charts plus big_number (which can show trend lines).
#   Valid time grains: P1D (day), P1W (week), P1M (month), P1Y (year),
#   P3M (quarterly), P1H (hour), P1D (daily), etc.
TIME_BASED_TYPES: set = {
    "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area",
    "echarts_timeseries_scatter", "mixed_timeseries", "waterfall",
    "big_number", "big_number_total",
}

# Valid time_grain_sqla values per Superset API
VALID_TIME_GRAINS: set = {
    "P1H", "PT1H",    # Hour
    "P1D", "PT1D",    # Day
    "P1W", "PT1W",    # Week
    "P1M", "PT1M",    # Month
    "P1Y", "PT1Y",    # Year
    "P3M",            # Quarter
    "P6M",            # Half-year
    "daily", "weekly", "monthly", "yearly",  # Legacy string formats
    "hour", "day", "week", "month", "year",  # Alternative formats
}
