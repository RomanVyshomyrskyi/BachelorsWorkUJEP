import pytest
import json

from modules.SupersetModule.rules import get_standard_chart_params


class TestGetStandardChartParams:
    # --- Viz Type Mapping Tests ---

    def test_line_maps_to_echarts_timeseries_line(self):
        params = get_standard_chart_params("line", 1)
        assert params["viz_type"] == "echarts_timeseries_line"

    def test_area_maps_to_echarts_area(self):
        """Area chart uses 'echarts_area' not 'echarts_timeseries_area'."""
        params = get_standard_chart_params("area", 1)
        assert params["viz_type"] == "echarts_area"

    def test_bar_maps_to_echarts_timeseries_bar(self):
        """Bar chart uses 'echarts_timeseries_bar' (time-based)."""
        params = get_standard_chart_params("bar", 1)
        assert params["viz_type"] == "echarts_timeseries_bar"

    def test_dist_bar_maps_to_echarts_timeseries_bar(self):
        params = get_standard_chart_params("dist_bar", 1)
        assert params["viz_type"] == "echarts_timeseries_bar"

    def test_big_number_maps_to_big_number(self):
        params = get_standard_chart_params("big_number", 1)
        assert params["viz_type"] == "big_number"

    def test_big_number_total_maps_to_big_number_total(self):
        params = get_standard_chart_params("big_number_total", 1)
        assert params["viz_type"] == "big_number_total"

    def test_scatter_maps_to_echarts_timeseries_scatter(self):
        params = get_standard_chart_params("scatter", 1)
        assert params["viz_type"] == "echarts_timeseries_scatter"

    def test_histogram_maps_to_histogram_v2(self):
        """Histogram uses 'histogram_v2' not 'echarts_timeseries_histogram'."""
        params = get_standard_chart_params("histogram", 1)
        assert params["viz_type"] == "histogram_v2"

    def test_waterfall_maps_to_waterfall(self):
        """Waterfall uses 'waterfall' not 'echarts_timeseries_waterfall'."""
        params = get_standard_chart_params("waterfall", 1)
        assert params["viz_type"] == "waterfall"

    def test_boxplot_maps_to_box_plot(self):
        """Box plot uses 'box_plot' not 'echarts_boxplot'."""
        params = get_standard_chart_params("boxplot", 1)
        assert params["viz_type"] == "box_plot"

    def test_graph_maps_to_graph_chart(self):
        """Graph uses 'graph_chart' not 'echarts_graph'."""
        params = get_standard_chart_params("graph", 1)
        assert params["viz_type"] == "graph_chart"

    def test_pie_maps_to_pie(self):
        params = get_standard_chart_params("pie", 1)
        assert params["viz_type"] == "pie"

    def test_table_maps_to_table(self):
        params = get_standard_chart_params("table", 1)
        assert params["viz_type"] == "table"

    def test_radar_maps_to_radar(self):
        params = get_standard_chart_params("radar", 1)
        assert params["viz_type"] == "radar"

    def test_heatmap_maps_to_heatmap_v2(self):
        params = get_standard_chart_params("heatmap", 1)
        assert params["viz_type"] == "heatmap_v2"

    def test_treemap_maps_to_treemap_v2(self):
        params = get_standard_chart_params("treemap", 1)
        assert params["viz_type"] == "treemap_v2"

    def test_sankey_maps_to_sankey_v2(self):
        params = get_standard_chart_params("sankey", 1)
        assert params["viz_type"] == "sankey_v2"

    def test_sunburst_maps_to_sunburst_v2(self):
        params = get_standard_chart_params("sunburst", 1)
        assert params["viz_type"] == "sunburst_v2"

    def test_funnel_maps_to_funnel(self):
        params = get_standard_chart_params("funnel", 1)
        assert params["viz_type"] == "funnel"

    def test_gauge_maps_to_gauge_chart(self):
        """Gauge uses 'gauge_chart' not 'gauge'."""
        params = get_standard_chart_params("gauge", 1)
        assert params["viz_type"] == "gauge_chart"

    def test_gantt_maps_to_gantt_chart(self):
        """Gantt uses 'gantt_chart' not 'gantt'."""
        params = get_standard_chart_params("gantt", 1)
        assert params["viz_type"] == "gantt_chart"

    def test_world_map_maps_to_world_map(self):
        params = get_standard_chart_params("world_map", 1)
        assert params["viz_type"] == "world_map"

    def test_word_cloud_maps_to_word_cloud(self):
        params = get_standard_chart_params("word_cloud", 1)
        assert params["viz_type"] == "word_cloud"

    def test_pivot_table_maps_to_pivot_table_v2(self):
        """Pivot table uses 'pivot_table_v2' not 'pivot_table'."""
        params = get_standard_chart_params("pivot_table", 1)
        assert params["viz_type"] == "pivot_table_v2"

    def test_parallel_maps_to_parallel(self):
        params = get_standard_chart_params("parallel", 1)
        assert params["viz_type"] == "parallel"

    def test_unknown_viz_type_unchanged(self):
        params = get_standard_chart_params("unknown_type", 1)
        assert params["viz_type"] == "unknown_type"

    # --- Time Series Specific Tests ---

    def test_echarts_timeseries_viz_types_have_x_axis_default(self):
        params = get_standard_chart_params("line", 1)
        assert "x_axis" in params
        assert params["x_axis"] == "order_date"

    def test_echarts_timeseries_viz_types_have_time_grain_default(self):
        params = get_standard_chart_params("line", 1)
        assert "time_grain_sqla" in params
        assert params["time_grain_sqla"] == "P1M"

    def test_non_time_series_no_x_axis(self):
        params = get_standard_chart_params("pie", 1)
        assert "x_axis" not in params

    def test_non_time_series_no_time_grain(self):
        params = get_standard_chart_params("pie", 1)
        assert "time_grain_sqla" not in params

    def test_custom_x_axis_override(self):
        params = get_standard_chart_params("line", 1, x_axis="date")
        assert params["x_axis"] == "date"

    def test_custom_time_grain_override(self):
        params = get_standard_chart_params("line", 1, time_grain_sqla="P1M")
        assert params["time_grain_sqla"] == "P1M"

    def test_bar_is_time_series(self):
        """Bar (echarts_timeseries_bar) IS a time-series chart and has x_axis."""
        params = get_standard_chart_params("bar", 1)
        assert "x_axis" in params
        assert "time_grain_sqla" in params

    def test_datasource_format(self):
        params = get_standard_chart_params("line", 42)
        assert params["datasource"] == "42__table"

    def test_row_limit_default(self):
        params = get_standard_chart_params("line", 1)
        assert params["row_limit"] == 10000

    def test_adhoc_filters_empty(self):
        params = get_standard_chart_params("line", 1)
        assert params["adhoc_filters"] == []

    def test_line_has_metrics_and_groupby(self):
        params = get_standard_chart_params("line", 1, metrics=["SUM(sales)"], groupby=["product_line"])
        assert params["metrics"] == ["SUM(sales)"]
        assert params["groupby"] == ["product_line"]

    def test_area_has_only_total(self):
        params = get_standard_chart_params("area", 1)
        assert params["only_total"] == True

    # --- Chart-Specific Params Tests ---

    def test_pie_has_groupby_and_metric(self):
        params = get_standard_chart_params("pie", 1, groupby=["product_line"], metric="SUM(sales)")
        assert params["groupby"] == ["product_line"]
        assert params["metric"] == "SUM(sales)"
        assert params["sort_by_metric"] == True

    def test_bubble_has_x_y_size(self):
        params = get_standard_chart_params("bubble", 1, x="SUM(quantity)", y="SUM(revenue)", size="count", series="category")
        assert params["x"] == "SUM(quantity)"
        assert params["y"] == "SUM(revenue)"
        assert params["size"] == "count"
        assert params["series"] == "category"

    def test_gantt_has_time_columns(self):
        params = get_standard_chart_params("gantt", 1, start_time="start", end_time="end", y_axis="status", series="priority")
        assert params["start_time"] == "start"
        assert params["end_time"] == "end"
        assert params["y_axis"] == "status"
        assert params["series"] == "priority"

    def test_graph_has_source_target(self):
        params = get_standard_chart_params("graph", 1, source="from", target="to", metric="count")
        assert params["source"] == "from"
        assert params["target"] == "to"
        assert params["metric"] == "count"
        assert params["layout"] == "circular"

    def test_sankey_has_source_target(self):
        params = get_standard_chart_params("sankey", 1, source="source_col", target="target_col")
        assert params["source"] == "source_col"
        assert params["target"] == "target_col"

    def test_table_has_query_mode_and_columns(self):
        params = get_standard_chart_params("table", 1)
        assert params["query_mode"] == "raw"
        assert "all_columns" in params

    def test_big_number_has_trend_config(self):
        params = get_standard_chart_params("big_number", 1, x_axis="order_date", show_trend_line=True)
        assert params["show_trend_line"] == True
        assert params["x_axis"] == "order_date"

    def test_big_number_total_simple(self):
        params = get_standard_chart_params("big_number_total", 1, metric="count")
        assert params["metric"] == "count"
        assert "show_trend_line" not in params

    def test_radar_has_metrics_list(self):
        params = get_standard_chart_params("radar", 1, metrics=["count", "AVG(sales)"], groupby=["product_line"])
        assert params["metrics"] == ["count", "AVG(sales)"]
        assert params["groupby"] == ["product_line"]

    def test_pivot_table_has_rows_and_columns(self):
        params = get_standard_chart_params("pivot_table", 1, groupby_rows=["country"], groupby_columns=["product_line"])
        assert params["groupbyRows"] == ["country"]
        assert params["groupbyColumns"] == ["product_line"]

    def test_mixed_timeseries_has_dual_metrics(self):
        params = get_standard_chart_params("mixed_timeseries", 1, metrics=["SUM(sales)"], metrics_b=["count"])
        assert "metrics" in params
        assert "metrics_b" in params

    def test_tree_chart_has_hierarchy_columns(self):
        params = get_standard_chart_params("tree", 1, id="id", parent="parent", name="name")
        assert params["id"] == "id"
        assert params["parent"] == "parent"
        assert params["name"] == "name"

    def test_histogram_has_column(self):
        params = get_standard_chart_params("histogram", 1, column="quantity", groupby=["deal_size"])
        assert params["column"] == "quantity"
        assert params["bins"] == 10

    def test_sunburst_has_columns(self):
        params = get_standard_chart_params("sunburst", 1, columns=["year", "product_line"])
        assert params["columns"] == ["year", "product_line"]

    def test_treemap_has_groupby(self):
        params = get_standard_chart_params("treemap", 1, groupby=["year", "product_line"])
        assert params["groupby"] == ["year", "product_line"]

    def test_box_plot_has_columns(self):
        params = get_standard_chart_params("box_plot", 1, columns=["order_date"], groupby=["product_line"])
        assert params["columns"] == ["order_date"]
        assert params["groupby"] == ["product_line"]

    def test_funnel_has_groupby(self):
        params = get_standard_chart_params("funnel", 1, groupby=["status"], metric="count")
        assert params["groupby"] == ["status"]
        assert params["sort_by_metric"] == True

    def test_heatmap_has_x_axis_and_groupby(self):
        params = get_standard_chart_params("heatmap", 1, x_axis="product_line", groupby="deal_size")
        assert params["x_axis"] == "product_line"
        assert params["groupby"] == "deal_size"

    def test_word_cloud_has_series(self):
        params = get_standard_chart_params("word_cloud", 1, series="customer_name")
        assert params["series"] == "customer_name"

    def test_gauge_has_groupby(self):
        params = get_standard_chart_params("gauge", 1, groupby=["deal_size"])
        assert params["groupby"] == ["deal_size"]
