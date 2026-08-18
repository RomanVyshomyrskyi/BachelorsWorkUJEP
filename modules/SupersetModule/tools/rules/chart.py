"""Chart creation rules for Superset MCP integration.

Provides the get_chart_creation_rules() function that returns
a comprehensive Markdown guide covering all 20+ Superset chart
types with their required parameters, metric formats, and
creation workflow.
"""


def get_chart_creation_rules() -> str:
    """Return comprehensive Markdown guide for creating Superset charts.
        Produces a structured reference document covering all 20+ Superset
        viz_types with their required and optional parameters, metric format
        specifications, creation workflow steps, and important notes about
        datasource format, row limits, and time grain values.

        This serves as both developer documentation and LLM context for the
        Superset automation tools.

    Returns:
        A Markdown string with sections: Chart Types & Required Params,
        Metric Format, Chart Creation Workflow, and Important Notes.
    """
    return """
# Superset Chart Creation Rules

## 1. Chart Types & Required Params

### Time Series Charts (line, bar, area, scatter)
- viz_type: `echarts_timeseries_line`, `echarts_timeseries_bar`, `echarts_area`, `echarts_timeseries_scatter`
- Required: `x_axis` (time column), `time_grain_sqla` (e.g., 'P1M'), `metrics` (list of strings)
- Optional: `groupby` (list of columns for series)
- Example: {"viz_type": "echarts_timeseries_line", "x_axis": "order_date", "time_grain_sqla": "P1M", "metrics": ["SUM(sales)"], "groupby": ["product_line"]}

### Mixed Timeseries (dual-axis)
- viz_type: `mixed_timeseries`
- Required: `x_axis`, `metrics` (primary), `metrics_b` (secondary)
- Example: {"viz_type": "mixed_timeseries", "x_axis": "order_date", "metrics": ["SUM(sales)"], "metrics_b": ["count"]}

### Bubble Chart
- viz_type: `bubble_v2`
- Required: `x`, `y`, `size` (string metrics), `series`, `entity`
- Example: {"viz_type": "bubble_v2", "x": "SUM(quantity_ordered)", "y": "SUM(sales)", "size": "count", "series": "product_line", "entity": "deal_size"}

### Pie Chart
- viz_type: `pie`
- Required: `groupby` (list), `metric` (string)
- Example: {"viz_type": "pie", "groupby": ["product_line"], "metric": "SUM(sales)"}

### Table Chart
- viz_type: `table`
- Required: `query_mode` ('raw'), `all_columns` (list of column names)
- Example: {"viz_type": "table", "query_mode": "raw", "all_columns": ["order_date", "product_line", "sales"]}

### Big Number
- viz_type: `big_number_total` (total), `big_number` (with trend)
- Required: `metric` (string)
- Example: {"viz_type": "big_number_total", "metric": "count"}
- With trend: {"viz_type": "big_number", "metric": "count", "show_trend_line": true, "x_axis": "order_date", "time_grain_sqla": "P1M"}

### Gauge Chart
- viz_type: `gauge_chart`
- Required: `groupby` (list), `metric` (string)
- Example: {"viz_type": "gauge_chart", "groupby": ["deal_size"], "metric": "count"}

### Gantt Chart
- viz_type: `gantt_chart`
- Required: `start_time`, `end_time`, `y_axis`, `series` (column names)
- Example: {"viz_type": "gantt_chart", "start_time": "start_time", "end_time": "end_time", "y_axis": "status", "series": "priority"}

### Box Plot
- viz_type: `box_plot`
- Required: `columns` (list with temporal column), `groupby` (list), `metrics` (list)
- Example: {"viz_type": "box_plot", "columns": ["order_date"], "groupby": ["product_line"], "metrics": ["count"]}

### Funnel Chart
- viz_type: `funnel`
- Required: `groupby` (list), `metric` (string)
- Example: {"viz_type": "funnel", "groupby": ["status"], "metric": "count"}

### Graph Chart (network)
- viz_type: `graph_chart`
- Required: `source`, `target` (column names), `metric` (string)
- Example: {"viz_type": "graph_chart", "source": "deal_size", "target": "product_line", "metric": "count"}

### Waterfall Chart
- viz_type: `waterfall`
- Required: `x_axis`, `time_grain_sqla`, `metric`
- Example: {"viz_type": "waterfall", "x_axis": "order_date", "time_grain_sqla": "P3M", "metric": "SUM(sales)"}

### Heatmap
- viz_type: `heatmap_v2`
- Required: `x_axis`, `groupby` (string), `metric` (string)
- Example: {"viz_type": "heatmap_v2", "x_axis": "product_line", "groupby": "deal_size", "metric": "count"}

### Histogram
- viz_type: `histogram_v2`
- Required: `column`, `groupby` (list)
- Optional: `bins` (default 10)
- Example: {"viz_type": "histogram_v2", "column": "quantity_ordered", "groupby": ["deal_size"], "bins": 10}

### Radar Chart
- viz_type: `radar`
- Required: `groupby` (list), `metrics` (list of strings)
- Example: {"viz_type": "radar", "groupby": ["product_line"], "metrics": ["count", "AVG(price_each)", "AVG(sales)"]}

### Sankey Diagram
- viz_type: `sankey_v2`
- Required: `source`, `target` (column names), `metric` (string)
- Example: {"viz_type": "sankey_v2", "source": "product_line", "target": "deal_size", "metric": "count"}

### Sunburst Chart
- viz_type: `sunburst_v2`
- Required: `columns` (list of hierarchical columns), `metric` (string)
- Example: {"viz_type": "sunburst_v2", "columns": ["year", "product_line"], "metric": "count"}

### TreeMap Chart
- viz_type: `treemap_v2`
- Required: `groupby` (list), `metric` (string)
- Example: {"viz_type": "treemap_v2", "groupby": ["year", "product_line"], "metric": "count"}

### Tree Chart (hierarchical)
- viz_type: `tree_chart`
- Required: `id`, `parent`, `name` (column names), `metric` (string)
- Example: {"viz_type": "tree_chart", "id": "id", "parent": "parent", "name": "name", "metric": "count"}

### Pivot Table
- viz_type: `pivot_table_v2`
- Required: `groupbyRows` (list), `groupbyColumns` (list), `metrics` (list)
- Example: {"viz_type": "pivot_table_v2", "groupbyRows": ["country", "city"], "groupbyColumns": ["product_line"], "metrics": ["SUM(sales)"]}

### Word Cloud
- viz_type: `word_cloud`
- Required: `series` (column name), `metric` (string)
- Example: {"viz_type": "word_cloud", "series": "customer_name", "metric": "count"}

### World Map
- viz_type: `world_map`
- Required: `groupby` (list), `metric` (string)
- Example: {"viz_type": "world_map", "groupby": ["country"], "metric": "SUM(sales)"}

## 2. Metric Format

- Use **simple string metrics**: "count", "SUM(sales)", "AVG(price_each)", "COUNT_DISTINCT(country)"
- The Superset API accepts string metrics for ALL chart types
- Format: `{AGGREGATION}({column_name})` or just "count" for row count
- Available aggregations: SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT

## 3. Chart Creation Workflow

1. Call `superset_get_standard_chart_params` with viz_type and datasource_id
2. Provide additional kwargs: metric, metrics, groupby, x_axis, etc.
3. The function returns a properly structured params dict
4. Use `json.dumps(params)` to create the JSON string
5. Call `generate_chart` with a config JSON that includes the params

Examples:
  params = get_standard_chart_params("line", 13, x_axis="order_date", time_grain_sqla="P1M", metrics=["SUM(sales)"], groupby=["product_line"])
  # Returns: {"datasource": "13__table", "viz_type": "echarts_timeseries_line", "metrics": ["SUM(sales)"], ...}
  params_json = json.dumps(params)  # Convert to JSON string for API
  create_chart(..., params=params_json)

## 4. Important Notes

- `datasource` field format: `"{datasource_id}__table"` (e.g., "13__table")
- `row_limit` defaults to 10000 for most charts
- `color_scheme` defaults to "supersetColors"
- All charts support `adhoc_filters` for WHERE clauses
- Time grain formats: P1D (day), P1W (week), P1M (month), P3M (quarter), P1Y (year)
"""
