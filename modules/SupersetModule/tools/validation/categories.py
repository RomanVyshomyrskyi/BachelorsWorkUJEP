"""
Viz type category sets for Superset chart parameter validation.

These 10 category sets classify every Superset chart viz_type by the
metric format it expects. Used by validate_chart_params to check format
correctness and by auto_fix_chart_params to apply the right conversions.
"""

from typing import Any, Dict

# Category 1: Chart types that expect a SINGLE STRING metric.
#   "metric": "count"  or  "metric": "SUM(sales)"
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
#   "metric": {"aggregate": "SUM", "column": {...}}
SINGULAR_ADHOC_METRIC_TYPES: set = {
    "pie",
    "waterfall",
}

# Category 3: Chart types that expect an ARRAY of string metrics.
#   "metrics": ["count", "SUM(col)"]
STRING_METRICS_ARRAY_TYPES: set = {
    "echarts_timeseries_line",
    "echarts_timeseries_bar",
    "echarts_area",
    "echarts_timeseries_scatter",
    "bubble_v2",
    "box_plot",
}

# Category 4: Chart types that expect an ARRAY of AdHocMetricObject dicts.
#   "metrics": [{"aggregate": "SUM", ...}]
ADHOC_METRICS_ARRAY_TYPES: set = {
    "mixed_timeseries",
    "pivot_table_v2",
}

# Category 5: Chart types that accept BOTH strings and objects in the metrics array.
MIXED_METRICS_TYPES: set = {
    "radar",
}

# Category 6: Chart types that have NO metric/metrics field at all.
NO_METRICS_TYPES: set = {
    "histogram_v2",
    "gantt_chart",
}

# Category 7: Requires an 'entity' field for geographic mapping.
ENTITY_REQUIRED_TYPES: set = {
    "world_map",
}

# Category 8: Requires source/target fields and validates DAG structure.
SANKEY_TYPES: set = {
    "sankey_v2",
}

# Category 9: Viz types that need specific datasource column types for compatibility.
#   Maps viz_type -> {required, optional, x_axis_temporal, description}
DATASOURCE_REQUIREMENTS: Dict[str, Dict[str, Any]] = {
    "world_map": {
        "required": ["entity"],
        "optional": ["groupby"],
        "description": "world_map needs entity field (geographic identifier like country_code, zipcode)",
    },
    "bubble_v2": {
        "required": ["x", "y", "size"],
        "optional": ["series", "entity"],
        "description": "bubble_v2 needs x, y, and size field references",
    },
    "heatmap_v2": {
        "required": ["x_axis", "groupby"],
        "optional": [],
        "description": "heatmap_v2 needs x_axis and groupby (row dimension)",
    },
    "sunburst_v2": {
        "required": ["columns"],
        "optional": ["metric"],
        "description": "sunburst_v2 needs columns field (array of hierarchy levels)",
    },
    "treemap_v2": {
        "required": [],
        "optional": ["groupby"],
        "description": "treemap_v2 works with groupby or columns for hierarchy",
    },
    "radar": {
        "required": ["groupby"],
        "optional": ["metrics"],
        "description": "radar needs groupby for dimension labels",
    },
    "box_plot": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "box_plot needs groupby for categories",
    },
    "histogram_v2": {
        "required": ["x_axis"],
        "optional": ["groupby", "metric"],
        "description": "histogram_v2 needs x_axis for the value to bin",
    },
    "waterfall": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "waterfall needs groupby for categories",
    },
    "funnel": {
        "required": ["groupby"],
        "optional": ["metric"],
        "description": "funnel needs groupby for steps",
    },
    "gauge_chart": {
        "required": [],
        "optional": ["groupby", "metric"],
        "description": "gauge_chart is flexible, works with count or custom metric",
    },
    "echarts_timeseries_line": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "description": "time series works best with temporal x_axis (date/time column)",
    },
    "echarts_area": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal": True,
        "description": "area chart works best with temporal x_axis (date/time column)",
    },
    "big_number": {
        "required": [],
        "optional": ["x_axis"],
        "x_axis_temporal_for_trendline": True,
        "description": "big_number with trendline needs temporal x_axis",
    },
}

# Category 10: Chart types that need granularity_sqla + time_range.
#   All time-based charts plus big_number (which can show trend lines).
TIME_BASED_TYPES: set = {
    "echarts_timeseries_line", "echarts_timeseries_bar", "echarts_area",
    "echarts_timeseries_scatter", "mixed_timeseries", "waterfall",
    "big_number", "big_number_total",
}
