"""
Timeseries chart strategies for Apache Superset.

Contains: Line, Bar, Area, Scatter, Bubble, MixedTimeseries
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy



"""
Timeseries chart strategies for Apache Superset.

Contains: Line, Bar, Area, Scatter, Bubble, MixedTimeseries
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy


class LineChartStrategy(ChartParamsStrategy):
    """
    Line chart strategy for time series data (echarts_timeseries_line).

    Description:
        Generates params for a time-based line chart with forecasting support.
        Suitable for showing trends over time with optional forecast periods
        and confidence intervals.
    """
    VIZ_TYPE = "echarts_timeseries_line"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1M",
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
        "seriesType": "echarts_timeseries_line",
        "opacity": 0.2,
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
        Build line chart params with user overrides applied to defaults.

        Description:
            Merges DEFAULTS with kwargs overrides, sets viz_type and datasource,
            then returns the complete params dict ready for Superset API.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metrics, groupby, x_axis, time_grain_sqla.

        Returns:
            Complete params dict for echarts_timeseries_line chart.
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


class BarChartStrategy(ChartParamsStrategy):
    """
    Bar chart strategy for time series data (echarts_timeseries_bar).

    Description:
        Generates params for a time-based bar chart with forecasting support.
        Similar to line chart but displays data as vertical bars.
    """
    VIZ_TYPE = "echarts_timeseries_bar"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1M",
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
        "orientation": "vertical",
        "only_total": True,
        "x_axis_title_margin": 15,
        "y_axis_title_margin": 15,
        "y_axis_title_position": "Left",
        "sort_series_type": "sum",
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "x_axis_time_format": "smart_date",
        "y_axis_format": "SMART_NUMBER",
        "truncateXAxis": True,
        "y_axis_bounds": [None, None],
        "rich_tooltip": True,
        "tooltipTimeFormat": "smart_date",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build bar chart params with user overrides applied to defaults.

        Description:
            Merges DEFAULTS with kwargs overrides, sets viz_type and datasource,
            then returns the complete params dict ready for Superset API.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metrics, groupby, x_axis, time_grain_sqla.

        Returns:
            Complete params dict for echarts_timeseries_bar chart.
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



class AreaChartStrategy(ChartParamsStrategy):
    """
    Area chart strategy (echarts_area).

    Description:
        Generates params for an area chart, which fills the area below the line
        with a semi-transparent color. Useful for showing cumulative trends over time.
    """
    VIZ_TYPE = "echarts_area"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1M",
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
        "seriesType": "echarts_timeseries_line",
        "opacity": 0.2,
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
        Build area chart params with user overrides applied to defaults.

        Description:
            Merges DEFAULTS with kwargs overrides, sets viz_type and datasource,
            then returns the complete params dict ready for Superset API.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metrics, groupby, x_axis, time_grain_sqla.

        Returns:
            Complete params dict for echarts_area chart.
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
