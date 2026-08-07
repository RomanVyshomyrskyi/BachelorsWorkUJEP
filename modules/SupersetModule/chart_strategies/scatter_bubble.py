"""
Scatter and bubble chart strategies for Apache Superset.

Contains: Scatter, Bubble, MixedTimeseries
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

class ScatterChartStrategy(ChartParamsStrategy):
    """
    Scatter plot strategy for time series data (echarts_timeseries_scatter).

    Description:
        Generates params for a time-based scatter plot, showing individual data
        points as circles over a time axis. Good for spotting outliers and patterns.
    """
    VIZ_TYPE = "echarts_timeseries_scatter"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1D",
        "x_axis_sort_asc": True,
        "x_axis_sort_series": "name",
        "x_axis_sort_series_ascending": True,
        "metrics": ["count"],
        "groupby": [],
        "order_desc": True,
        "truncate_metric": True,
        "show_empty_columns": True,
        "comparison_type": "values",
        "annotation_layers": [],
        "forecastPeriods": 10,
        "forecastInterval": 0.8,
        "only_total": True,
        "markerSize": 6,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "tooltipTimeFormat": "smart_date",
        "y_axis_format": "SMART_NUMBER",
        "truncateXAxis": True,
        "y_axis_bounds": [None, None],
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build scatter plot params with user overrides applied to defaults.

        Description:
            Merges DEFAULTS with kwargs overrides, sets viz_type and datasource,
            then returns the complete params dict ready for Superset API. Uses
            daily time grain (P1D) by default for finer scatter granularity.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metrics, groupby, x_axis, time_grain_sqla.

        Returns:
            Complete params dict for echarts_timeseries_scatter chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class BubbleChartStrategy(ChartParamsStrategy):
    """
    Bubble chart strategy (bubble_v2).

    Description:
        Generates params for a bubble chart showing 3 dimensions: x, y, and bubble size.
        Requires x, y, and size fields, plus an optional series for color grouping.
    """
    VIZ_TYPE = "bubble_v2"
    DEFAULTS = {
        "series": "product_line",
        "entity": "deal_size",
        "x": "SUM(quantity_ordered)",
        "y": "COUNT_DISTINCT(country)",
        "size": "count",
        "order_desc": True,
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "max_bubble_size": "25",
        "tooltipSizeFormat": "SMART_NUMBER",
        "opacity": 0.6,
        "x_axis_title_margin": 30,
        "xAxisFormat": "SMART_NUMBER",
        "y_axis_title_margin": 30,
        "y_axis_format": "SMART_NUMBER",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build bubble chart params with user overrides applied to defaults.

        Description:
            Sets x, y, size axis fields and series for color grouping.
            These are bubble-specific fields not present in other chart types.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: series, entity, x, y, size.

        Returns:
            Complete params dict for bubble_v2 chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["series"] = kwargs.get("series", d["series"])
        d["entity"] = kwargs.get("entity", d["entity"])
        d["x"] = kwargs.get("x", d["x"])
        d["y"] = kwargs.get("y", d["y"])
        d["size"] = kwargs.get("size", d["size"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class MixedTimeseriesStrategy(ChartParamsStrategy):
    """
    Mixed timeseries strategy (mixed_timeseries).

    Description:
        Generates params for a dual-axis chart combining two different chart types
        (e.g., line + bar) on shared time axis. Requires metrics (primary) and metrics_b (secondary).
    """
    VIZ_TYPE = "mixed_timeseries"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1M",
        "metrics": ["SUM(sales)"],
        "groupby": [],
        "metrics_b": ["count"],
        "groupby_b": [],
        "seriesType": "echarts_timeseries_line",
        "opacity": 0.2,
        "markerSize": 6,
        "yAxisIndex": 1,
        "seriesTypeB": "echarts_timeseries_bar",
        "opacityB": 0.2,
        "markerSizeB": 6,
        "yAxisIndexB": 0,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "rich_tooltip": True,
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build mixed timeseries params with dual-axis configuration.

        Description:
            Sets primary metrics (metrics) and secondary metrics (metrics_b),
            each with their own groupby, series type, and visual properties.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metrics, groupby, metrics_b, groupby_b, seriesType, seriesTypeB, x_axis, time_grain_sqla.

        Returns:
            Complete params dict for mixed_timeseries chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metrics_b"] = kwargs.get("metrics_b", d["metrics_b"])
        d["groupby_b"] = kwargs.get("groupby_b", d["groupby_b"])
        d["seriesType"] = kwargs.get("seriesType", d["seriesType"])
        d["seriesTypeB"] = kwargs.get("seriesTypeB", d["seriesTypeB"])
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base
