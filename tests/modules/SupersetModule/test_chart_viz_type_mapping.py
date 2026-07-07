import pytest
import json

from modules.SupersetModule.rules import get_standard_chart_params


class TestGetStandardChartParams:
    def test_line_maps_to_echarts_timeseries_line(self):
        params = get_standard_chart_params("line", 1)
        assert params["viz_type"] == "echarts_timeseries_line"

    def test_area_maps_to_echarts_timeseries_area(self):
        params = get_standard_chart_params("area", 1)
        assert params["viz_type"] == "echarts_timeseries_area"
        assert params.get("show_area") == True
        assert params.get("stack") == "Stack"

    def test_bar_maps_to_echarts_bar(self):
        params = get_standard_chart_params("bar", 1)
        assert params["viz_type"] == "echarts_bar"

    def test_dist_bar_maps_to_echarts_timeseries_bar(self):
        params = get_standard_chart_params("dist_bar", 1)
        assert params["viz_type"] == "echarts_timeseries_bar"

    def test_big_number_maps_to_big_number(self):
        params = get_standard_chart_params("big_number", 1)
        assert params["viz_type"] == "big_number"

    def test_scatter_maps_to_echarts_timeseries_scatter(self):
        params = get_standard_chart_params("scatter", 1)
        assert params["viz_type"] == "echarts_timeseries_scatter"

    def test_histogram_maps_to_echarts_timeseries_histogram(self):
        params = get_standard_chart_params("histogram", 1)
        assert params["viz_type"] == "echarts_timeseries_histogram"

    def test_waterfall_maps_to_echarts_timeseries_waterfall(self):
        params = get_standard_chart_params("waterfall", 1)
        assert params["viz_type"] == "echarts_timeseries_waterfall"

    def test_boxplot_maps_to_echarts_boxplot(self):
        params = get_standard_chart_params("boxplot", 1)
        assert params["viz_type"] == "echarts_boxplot"

    def test_graph_maps_to_echarts_graph(self):
        params = get_standard_chart_params("graph", 1)
        assert params["viz_type"] == "echarts_graph"

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

    def test_gauge_maps_to_gauge(self):
        params = get_standard_chart_params("gauge", 1)
        assert params["viz_type"] == "gauge"

    def test_gantt_maps_to_gantt(self):
        params = get_standard_chart_params("gantt", 1)
        assert params["viz_type"] == "gantt"

    def test_world_map_maps_to_world_map(self):
        params = get_standard_chart_params("world_map", 1)
        assert params["viz_type"] == "world_map"

    def test_word_cloud_maps_to_word_cloud(self):
        params = get_standard_chart_params("word_cloud", 1)
        assert params["viz_type"] == "word_cloud"

    def test_pivot_table_maps_to_pivot_table(self):
        params = get_standard_chart_params("pivot_table", 1)
        assert params["viz_type"] == "pivot_table"

    def test_parallel_maps_to_parallel(self):
        params = get_standard_chart_params("parallel", 1)
        assert params["viz_type"] == "parallel"

    def test_unknown_viz_type_unchanged(self):
        params = get_standard_chart_params("unknown_type", 1)
        assert params["viz_type"] == "unknown_type"

    def test_echarts_timeseries_viz_types_have_x_axis_default(self):
        params = get_standard_chart_params("line", 1)
        assert "x_axis" in params
        assert params["x_axis"] == "year"

    def test_echarts_timeseries_viz_types_have_time_grain_default(self):
        params = get_standard_chart_params("line", 1)
        assert "time_grain_sqla" in params
        assert params["time_grain_sqla"] == "P1Y"

    def test_non_echarts_viz_types_no_x_axis(self):
        params = get_standard_chart_params("pie", 1)
        assert "x_axis" not in params

    def test_non_echarts_viz_types_no_time_grain(self):
        params = get_standard_chart_params("pie", 1)
        assert "time_grain_sqla" not in params

    def test_custom_x_axis_override(self):
        params = get_standard_chart_params("line", 1, x_axis="date")
        assert params["x_axis"] == "date"

    def test_custom_time_grain_override(self):
        params = get_standard_chart_params("line", 1, time_grain_sqla="P1M")
        assert params["time_grain_sqla"] == "P1M"

    def test_datasource_format(self):
        params = get_standard_chart_params("line", 42)
        assert params["datasource"] == "42__table"

    def test_row_limit_default(self):
        params = get_standard_chart_params("line", 1)
        assert params["row_limit"] == 1000

    def test_adhoc_filters_empty(self):
        params = get_standard_chart_params("line", 1)
        assert params["adhoc_filters"] == []

    def test_groupby_to_x_axis_conversion(self):
        params = get_standard_chart_params("line", 1, groupby=["product"])
        assert params["x_axis"] == "product"

    def test_groupby_string_to_x_axis_conversion(self):
        params = get_standard_chart_params("line", 1, groupby="product")
        assert params["x_axis"] == "product"

    def test_bar_has_no_x_axis_or_time_grain(self):
        params = get_standard_chart_params("bar", 1)
        assert "x_axis" not in params
        assert "time_grain_sqla" not in params
