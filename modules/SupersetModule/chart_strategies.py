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
import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Base strategy – every chart type follows the exact same interface
# ─────────────────────────────────────────────────────────────────────────────

class ChartParamsStrategy(ABC):
    """
    Base strategy – every chart type must implement `build()`.

    Description:
        Abstract base class that defines the interface for all chart parameter
        generation strategies. Each concrete strategy sets VIZ_TYPE (the actual
        Superset viz_type string), DEFAULTS (default parameter values), and
        implements build() to produce a complete params dict.

    Attributes:
        VIZ_TYPE: The actual Superset viz_type string (e.g. "echarts_timeseries_line").
        DEFAULTS: Dict of default parameter values for this chart type.
        REQUIRED: List of parameter names that must be present in the output.
    """

    VIZ_TYPE: str = ""
    DEFAULTS: Dict[str, Any] = {}
    REQUIRED: List[str] = []

    @abstractmethod
    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Return a fully-formed params dict for the Superset chart API.

        Description:
            Abstract method that must be implemented by every concrete strategy.
            Produces a complete params dict that can be serialized to JSON and
            sent to Superset's chart creation API.

        Args:
            datasource_id: The Superset datasource/table ID to query.
            **kwargs: Optional overrides for DEFAULTS values (metrics, groupby, x_axis, etc.).

        Returns:
            A dict with keys like 'datasource', 'viz_type', 'metrics', 'groupby', etc.
        """
        ...

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _base(datasource_id: int, row_limit: int = 10000) -> Dict[str, Any]:
        """
        Common base keys all strategies start from.

        Description:
            Returns the foundational dict structure shared by every chart type,
            including the datasource reference string, empty filter array, and row limit.

        Args:
            datasource_id: The Superset datasource ID (e.g. 13).
            row_limit: Maximum number of rows to return (default 10000).

        Returns:
            Base dict with 'datasource', 'adhoc_filters', and 'row_limit' keys.
        """
        # Construct datasource reference string in Superset's expected format: "{id}__table"
        return {
            "datasource": f"{datasource_id}__table",
            "adhoc_filters": [],
            "row_limit": row_limit,
        }

    @staticmethod
    def _normalize_groupby(val: Any) -> List[str]:
        """
        Ensure groupby is always a list (or empty list).

        Description:
            Superset's chart API expects groupby to be a list of column name strings.
            This helper accepts a string, list, or None and always returns a list.

        Args:
            val: Value to normalize – can be str, list, or any other type.

        Returns:
            A list of column name strings, or empty list if val is not str/list.
        """
        if isinstance(val, list):
            return val  # Already a list, return as-is
        if isinstance(val, str):
            return [val]  # Single string → wrap in list
        return []  # None or unexpected type → empty list

    @staticmethod
    def _defaults() -> Dict[str, Any]:
        """
        Merge strategy defaults – overrideable by kwargs.

        Description:
            Retrieves the DEFAULTS dict from the first concrete subclass.
            Used internally for initialization and default value resolution.

        Returns:
            Dict of default parameter values from the first registered strategy, or empty dict.
        """
        return dict(ChartParamsStrategy.__subclasses__()[0].DEFAULTS) if ChartParamsStrategy.__subclasses__() else {}


# ─────────────────────────────────────────────────────────────────────────────
#  1.  Line  –  echarts_timeseries_line
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metrics if provided, otherwise use default ["count"]
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Normalize groupby to always be a list
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override x_axis column if provided (defaults to "order_date")
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        # Override time grain (defaults to monthly "P1M")
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  2.  Bar  –  echarts_timeseries_bar
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metrics if provided, otherwise use default ["count"]
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Normalize groupby to always be a list
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override x_axis column and time grain from kwargs
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  3.  Area  –  echarts_area
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metrics if provided, otherwise use defaults
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Normalize groupby to always be a list
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override x_axis column and time grain from kwargs
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  4.  Scatter  –  echarts_timeseries_scatter
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metrics if provided, otherwise use defaults
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Normalize groupby to always be a list
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override x_axis column and time grain from kwargs
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  5.  Bubble  –  bubble_v2
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override bubble-specific fields: series (color grouping), entity, x, y, size axes
        d["series"] = kwargs.get("series", d["series"])
        d["entity"] = kwargs.get("entity", d["entity"])
        d["x"] = kwargs.get("x", d["x"])
        d["y"] = kwargs.get("y", d["y"])
        d["size"] = kwargs.get("size", d["size"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  6.  Pie  –  pie
# ─────────────────────────────────────────────────────────────────────────────

class PieChartStrategy(ChartParamsStrategy):
    """
    Pie chart strategy (pie).

    Description:
        Generates params for a pie/donut chart showing proportions of categories.
        Requires a groupby column for slices and a metric for slice sizes.
    """
    VIZ_TYPE = "pie"
    DEFAULTS = {
        "groupby": ["product_line"],
        "metric": "SUM(sales)",
        "sort_by_metric": True,
        "show_labels_threshold": 5,
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "label_type": "key",
        "number_format": "SMART_NUMBER",
        "date_format": "smart_date",
        "show_labels": True,
        "labels_outside": True,
        "outerRadius": 70,
        "innerRadius": 30,
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build pie chart params with user overrides applied to defaults.

        Description:
            Merges DEFAULTS with kwargs overrides for groupby (slice categories)
            and metric (slice sizes), sets viz_type and datasource, then returns
            the complete params dict ready for Superset API.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for pie chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (slices of the pie)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided, otherwise use default
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  7.  Table  –  table
# ─────────────────────────────────────────────────────────────────────────────

class TableChartStrategy(ChartParamsStrategy):
    """
    Table chart strategy (table).

    Description:
        Generates params for a data table display. Shows raw data rows with
        configurable columns, sorting, and pagination. Uses query_mode='raw'.
    """
    VIZ_TYPE = "table"
    DEFAULTS = {
        "query_mode": "raw",
        "groupby": [],
        "time_grain_sqla": "P1D",
        "temporal_columns_lookup": {"order_date": True},
        "all_columns": ["order_date", "product_line", "status", "price_each", "sales"],
        "percent_metrics": [],
        "order_by_cols": [],
        "server_page_length": 10,
        "order_desc": True,
        "table_timestamp_format": "smart_date",
        "show_cell_bars": True,
        "color_pn": True,
        "allow_render_html": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build table chart params with user overrides applied to defaults.

        Description:
            Table charts have a lower default row_limit (1000) and require
            all_columns and order_by_cols configuration for proper display.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, all_columns, order_by_cols.

        Returns:
            Complete params dict for table chart (row_limit=1000).
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["all_columns"] = kwargs.get("all_columns", d["all_columns"])
        d["order_by_cols"] = kwargs.get("order_by_cols", d["order_by_cols"])
        # Table charts use a lower row_limit (1000) since they display full rows
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  8.  Big Number  –  big_number (with trend line)
# ─────────────────────────────────────────────────────────────────────────────

class BigNumberChartStrategy(ChartParamsStrategy):
    """
    Big Number chart strategy with optional trend line (big_number).

    Description:
        Generates params for a KPI card showing a single metric value,
        optionally with a trend line over time.
    """
    VIZ_TYPE = "big_number"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P1M",
        "metric": "count",
        "show_trend_line": False,
        "start_y_axis_at_zero": True,
        "color_picker": {"r": 0, "g": 122, "b": 135, "a": 1},
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
        "time_format": "smart_date",
        "rolling_type": "None",
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build big_number chart params with trend line support.

        Description:
            Sets metric, optional time axis for trend line, time grain, and
            trend line toggle. Supports color customization and font sizing.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metric, x_axis, time_grain_sqla, show_trend_line.

        Returns:
            Complete params dict for big_number chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metric, x_axis, time grain, and trend line toggle from kwargs
        d["metric"] = kwargs.get("metric", d["metric"])
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        d["show_trend_line"] = kwargs.get("show_trend_line", d["show_trend_line"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  9.  Big Number Total  –  big_number_total
# ─────────────────────────────────────────────────────────────────────────────

class BigNumberTotalStrategy(ChartParamsStrategy):
    """
    Big Number Total chart strategy (big_number_total).

    Description:
        Generates params for a KPI card showing a single total value without trend line.
        Simpler than big_number — only requires a metric.
    """
    VIZ_TYPE = "big_number_total"
    DEFAULTS = {
        "metric": "count",
        "header_font_size": 0.4,
        "subheader_font_size": 0.15,
        "y_axis_format": "SMART_NUMBER",
        "time_format": "smart_date",
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build big_number_total chart params.

        Description:
            Merges big_number_total DEFAULTS with kwargs overrides, sets viz_type
            and datasource, then returns the complete params dict. Simpler than
            big_number — only requires a metric, with no trend line or time axis.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: metric.

        Returns:
            Complete params dict for big_number_total chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Override metric if provided, otherwise use default
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  10. Gauge  –  gauge_chart
# ─────────────────────────────────────────────────────────────────────────────

class GaugeChartStrategy(ChartParamsStrategy):
    """
    Gauge chart strategy (gauge_chart).

    Description:
        Generates params for a gauge/meter visualization showing a single value
        against a defined range. Useful for KPIs with targets.
    """
    VIZ_TYPE = "gauge_chart"
    DEFAULTS = {
        "groupby": ["deal_size"],
        "metric": "count",
        "row_limit": 10,
        "start_angle": 225,
        "end_angle": -45,
        "color_scheme": "supersetColors",
        "font_size": 13,
        "number_format": "SMART_NUMBER",
        "value_formatter": "{value}",
        "show_pointer": True,
        "animation": True,
        "show_progress": True,
        "overlap": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build gauge chart params with groupby categories and a metric value.

        Description:
            Merges DEFAULTS with kwargs overrides. The gauge chart shows a single
            metric value against a range, visualized as a speedometer-like dial.
            Groupby defines the gauge segments/categories.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for gauge_chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (gauge segments/categories)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided, otherwise use default
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  11. Gantt  –  gantt_chart
# ─────────────────────────────────────────────────────────────────────────────

class GanttChartStrategy(ChartParamsStrategy):
    """
    Gantt chart strategy (gantt_chart).

    Description:
        Generates params for a Gantt/timeline chart showing tasks with start/end times.
        Requires start_time, end_time, y_axis (category), and series (color groups).
    """
    VIZ_TYPE = "gantt_chart"
    DEFAULTS = {
        "start_time": "start_time",
        "end_time": "end_time",
        "y_axis": "status",
        "series": "priority",
        "subcategories": True,
        "x_axis_time_bounds": ["08:00:00", "19:00:00"],
        "x_axis_time_format": "smart_date",
        "tooltipTimeFormat": "smart_date",
        "tooltipValuesFormat": "SMART_NUMBER",
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendType": "plain",
        "legendOrientation": "right",
        "zoomable": False,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build Gantt chart params with timeline fields.

        Description:
            Sets start_time, end_time columns, y_axis category, and series color grouping.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: start_time, end_time, y_axis, series.

        Returns:
            Complete params dict for gantt_chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set timeline fields: start_time, end_time, y_axis (category), series (color groups)
        d["start_time"] = kwargs.get("start_time", d["start_time"])
        d["end_time"] = kwargs.get("end_time", d["end_time"])
        d["y_axis"] = kwargs.get("y_axis", d["y_axis"])
        d["series"] = kwargs.get("series", d["series"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  12. Box Plot  –  box_plot
# ─────────────────────────────────────────────────────────────────────────────

class BoxPlotStrategy(ChartParamsStrategy):
    """
    Box plot strategy (box_plot).

    Description:
        Generates params for a box-and-whisker plot showing data distribution
        by category. Requires columns (temporal), groupby categories, and metrics.
    """
    VIZ_TYPE = "box_plot"
    DEFAULTS = {
        "columns": ["order_date"],
        "time_grain_sqla": "P1D",
        "temporal_columns_lookup": {"order_date": True},
        "groupby": ["product_line"],
        "metrics": ["count"],
        "whiskerOptions": "Tukey",
        "color_scheme": "supersetColors",
        "number_format": "SMART_NUMBER",
        "date_format": "smart_date",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build box plot params with columns, groupby, and metrics.

        Description:
            Sets temporal columns lookup automatically from the first column,
            normalizes groupby to list, and accepts metric overrides.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: columns, column (fallback), groupby, metrics.

        Returns:
            Complete params dict for box_plot.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Support both 'columns' and 'column' kwarg for convenience
        d["columns"] = kwargs.get("columns", [kwargs.get("column", d["columns"][0])])
        # Normalize groupby to always be a list (categories on the box plot axis)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metrics if provided
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Auto-populate temporal columns lookup from first column
        d["temporal_columns_lookup"] = {d["columns"][0]: True}
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  13. Funnel  –  funnel
# ─────────────────────────────────────────────────────────────────────────────

class FunnelStrategy(ChartParamsStrategy):
    """
    Funnel chart strategy (funnel).

    Description:
        Generates params for a funnel visualization showing stages of a process
        (e.g., sales pipeline). Each groupby category becomes a stage.
    """
    VIZ_TYPE = "funnel"
    DEFAULTS = {
        "groupby": ["status"],
        "metric": "count",
        "row_limit": 10,
        "sort_by_metric": True,
        "percent_calculation_type": "first_step",
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendOrientation": "top",
        "legend_margin": 50,
        "show_labels": True,
        "show_tooltip_labels": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build funnel chart params with stage categories and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The funnel chart shows
            sequential stages (from groupby categories) sized by metric values,
            illustrating process flow and drop-off between stages.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for funnel chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (funnel stages)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided, otherwise use default
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  14. Graph  –  graph_chart
# ─────────────────────────────────────────────────────────────────────────────

class GraphChartStrategy(ChartParamsStrategy):
    """
    Graph/network chart strategy (graph_chart).

    Description:
        Generates params for a network/graph visualization showing relationships
        between entities. Requires source and target columns.
    """
    VIZ_TYPE = "graph_chart"
    DEFAULTS = {
        "source": "deal_size",
        "target": "product_line",
        "metric": "count",
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "layout": "circular",
        "edgeSymbol": "none,arrow",
        "roam": True,
        "selectedMode": "single",
        "baseNodeSize": 20,
        "baseEdgeWidth": 3,
        "edgeLength": 400,
        "gravity": 0.3,
        "repulsion": 1000,
        "friction": 0.2,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build graph/network chart params with source, target, and metric.

        Description:
            Sets the source and target columns for edges, the metric for edge weight,
            and optional layout algorithm (circular, force-directed, etc.).

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: source, target, metric, layout.

        Returns:
            Complete params dict for graph_chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set graph/network fields: source and target for edges, metric for edge weight
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        # Override layout algorithm (circular, force, etc.)
        d["layout"] = kwargs.get("layout", d["layout"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  15. Waterfall  –  waterfall
# ─────────────────────────────────────────────────────────────────────────────

class WaterfallStrategy(ChartParamsStrategy):
    """
    Waterfall chart strategy (waterfall).

    Description:
        Generates params for a waterfall chart showing cumulative effect of
        positive and negative values over time. Requires x_axis, time_grain, and metric.
    """
    VIZ_TYPE = "waterfall"
    DEFAULTS = {
        "x_axis": "order_date",
        "time_grain_sqla": "P3M",
        "groupby": [],
        "metric": "SUM(sales)",
        "show_value": True,
        "increase_color": {"r": 90, "g": 193, "b": 137, "a": 1},
        "decrease_color": {"r": 224, "g": 67, "b": 85, "a": 1},
        "total_color": {"r": 102, "g": 102, "b": 102, "a": 1},
        "x_axis_time_format": "smart_date",
        "x_ticks_layout": "auto",
        "y_axis_format": "SMART_NUMBER",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build waterfall chart params with time axis and metric.

        Description:
            Sets x_axis for time dimension, time_grain_sqla for aggregation level,
            optional groupby for series, and metric for values.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: x_axis, time_grain_sqla, groupby, metric.

        Returns:
            Complete params dict for waterfall chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set time axis fields: x_axis column, time grain for aggregation level
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Normalize groupby to always be a list (optional series dimension)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided (value shown per waterfall step)
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  16. Heatmap  –  heatmap_v2
# ─────────────────────────────────────────────────────────────────────────────

class HeatmapStrategy(ChartParamsStrategy):
    """
    Heatmap chart strategy (heatmap_v2).

    Description:
        Generates params for a heatmap showing values as color intensity across
        a grid of x_axis categories and groupby rows.
    """
    VIZ_TYPE = "heatmap_v2"
    DEFAULTS = {
        "x_axis": "product_line",
        "time_grain_sqla": "P1D",
        "groupby": "deal_size",
        "metric": "count",
        "sort_x_axis": "alpha_asc",
        "sort_y_axis": "alpha_asc",
        "show_legend": True,
        "show_percentage": True,
        "show_values": True,
        "y_axis_format": "SMART_NUMBER",
        "x_axis_time_format": "smart_date",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build heatmap chart params with x_axis, groupby, and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The heatmap displays values as
            color intensity across a grid formed by x_axis (columns) and groupby
            (rows), sized by the metric.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: x_axis, groupby, metric.

        Returns:
            Complete params dict for heatmap_v2 chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set heatmap grid dimensions: x_axis (columns), groupby (rows)
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["groupby"] = kwargs.get("groupby", d["groupby"])
        # Override metric if provided (color intensity)
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  17. Histogram  –  histogram_v2
# ─────────────────────────────────────────────────────────────────────────────

class HistogramStrategy(ChartParamsStrategy):
    """
    Histogram chart strategy (histogram_v2).

    Description:
        Generates params for a histogram showing the distribution of a numeric column
        by binning values. Requires a column to histogram and optional groupby for segmentation.
    """
    VIZ_TYPE = "histogram_v2"
    DEFAULTS = {
        "column": "quantity_ordered",
        "groupby": [],
        "bins": 10,
        "normalize": False,
        "color_scheme": "supersetColors",
        "show_value": False,
        "show_legend": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build histogram chart params with column, groupby, and bin count.

        Description:
            Merges DEFAULTS with kwargs overrides. The histogram visualizes the
            distribution of a numeric column by binning values and showing counts
            per bin. Optional groupby adds segmentation.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: column, groupby, bins.

        Returns:
            Complete params dict for histogram_v2 chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set the column to histogram and normalize groupby for segmentation
        d["column"] = kwargs.get("column", d["column"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override bin count if provided (controls histogram resolution)
        d["bins"] = kwargs.get("bins", d["bins"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  18. Radar  –  radar
# ─────────────────────────────────────────────────────────────────────────────

class RadarStrategy(ChartParamsStrategy):
    """
    Radar chart strategy (radar).

    Description:
        Generates params for a radar/spider chart showing multiple metrics across
        categories. Requires groupby for dimension labels and metrics for axes.
    """
    VIZ_TYPE = "radar"
    DEFAULTS = {
        "groupby": ["product_line"],
        "metrics": ["count"],
        "row_limit": 10,
        "color_scheme": "supersetColors",
        "show_legend": True,
        "legendType": "scroll",
        "legendOrientation": "top",
        "show_labels": False,
        "label_type": "value",
        "label_position": "top",
        "number_format": "SMART_NUMBER",
        "date_format": "smart_date",
        "is_circle": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build radar chart params with groupby categories and multiple metrics.

        Description:
            Merges DEFAULTS with kwargs overrides. The radar/spider chart plots
            multiple metrics on separate axes for each groupby category, allowing
            visual comparison across dimensions.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metrics.

        Returns:
            Complete params dict for radar chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (radar axes/categories)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metrics if provided (one axis per metric)
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  19. Sankey  –  sankey_v2
# ─────────────────────────────────────────────────────────────────────────────

class SankeyStrategy(ChartParamsStrategy):
    """
    Sankey diagram strategy (sankey_v2).

    Description:
        Generates params for a Sankey diagram showing flow between source and target
        nodes. Requires source, target columns and a metric for flow magnitude.
    """
    VIZ_TYPE = "sankey_v2"
    DEFAULTS = {
        "source": "product_line",
        "target": "deal_size",
        "metric": "count",
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build Sankey diagram params with source, target, and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The Sankey diagram shows flow
            between source and target nodes, with the metric representing flow
            magnitude (visualized as link width).

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: source, target, metric.

        Returns:
            Complete params dict for sankey_v2 chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set Sankey-specific fields: source, target nodes, and flow metric
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  20. Sunburst  –  sunburst_v2
# ─────────────────────────────────────────────────────────────────────────────

class SunburstStrategy(ChartParamsStrategy):
    """
    Sunburst chart strategy (sunburst_v2).

    Description:
        Generates params for a sunburst diagram showing hierarchical data as concentric rings.
        Requires columns field defining the hierarchy levels and a metric for slice sizes.
    """
    VIZ_TYPE = "sunburst_v2"
    DEFAULTS = {
        "columns": ["year", "product_line"],
        "metric": "count",
        "color_scheme": "supersetColors",
        "linear_color_scheme": "superset_seq_1",
        "show_labels": True,
        "show_labels_threshold": 5,
        "label_type": "key",
        "number_format": "~g",
        "date_format": "smart_date",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build sunburst chart params with hierarchical columns and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The sunburst chart displays
            hierarchical data as concentric rings. The columns field defines the
            hierarchy levels (outer to inner), and the metric sizes each segment.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: columns (hierarchy levels), metric.

        Returns:
            Complete params dict for sunburst_v2 chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set hierarchy columns (from outer to inner ring) and metric for segment size
        d["columns"] = kwargs.get("columns", d["columns"])
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  21. TreeMap  –  treemap_v2
# ─────────────────────────────────────────────────────────────────────────────

class TreeMapStrategy(ChartParamsStrategy):
    """
    TreeMap chart strategy (treemap_v2).

    Description:
        Generates params for a treemap showing hierarchical data as nested rectangles.
        Uses groupby for hierarchy levels and metric for rectangle sizes.
    """
    VIZ_TYPE = "treemap_v2"
    DEFAULTS = {
        "groupby": ["year", "product_line"],
        "metric": "count",
        "color_scheme": "supersetColors",
        "show_labels": True,
        "show_upper_labels": True,
        "label_type": "key_value",
        "number_format": "SMART_NUMBER",
        "date_format": "smart_date",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build treemap chart params with groupby hierarchy and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The treemap shows hierarchical
            data as nested rectangles, with groupby defining the hierarchy levels
            and metric sizing each rectangle.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for treemap_v2 chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (hierarchy levels for nesting)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided (rectangle size)
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  22. Tree  –  tree_chart
# ─────────────────────────────────────────────────────────────────────────────

class TreeStrategy(ChartParamsStrategy):
    """
    Tree chart strategy (tree_chart).

    Description:
        Generates params for a hierarchical tree visualization showing parent-child
        relationships. Requires id, parent, name columns and optional layout algorithm.
    """
    VIZ_TYPE = "tree_chart"
    DEFAULTS = {
        "id": "id",
        "parent": "parent",
        "name": "name",
        "root_node_id": "1",
        "metric": "count",
        "layout": "radial",
        "node_label_position": "top",
        "child_label_position": "top",
        "symbol": "emptyCircle",
        "symbolSize": 7,
        "roam": False,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build tree chart params with hierarchical node columns and metric.

        Description:
            Sets id, parent, and name columns for the tree structure,
            plus optional layout algorithm (radial, compact, etc.).

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: id, parent, name, metric, layout.

        Returns:
            Complete params dict for tree_chart (row_limit=1000).
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["id"] = kwargs.get("id", d["id"])
        d["parent"] = kwargs.get("parent", d["parent"])
        d["name"] = kwargs.get("name", d["name"])
        d["metric"] = kwargs.get("metric", d["metric"])
        d["layout"] = kwargs.get("layout", d["layout"])
        # Tree charts use a lower row_limit since they display full hierarchy
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  23. Pivot Table  –  pivot_table_v2
# ─────────────────────────────────────────────────────────────────────────────

class PivotTableStrategy(ChartParamsStrategy):
    """
    Pivot table strategy (pivot_table_v2).

    Description:
        Generates params for a pivot table with rows, columns, and aggregated metrics.
        Requires groupbyRows, groupbyColumns, and metrics configuration.
    """
    VIZ_TYPE = "pivot_table_v2"
    DEFAULTS = {
        "groupbyColumns": ["product_line"],
        "groupbyRows": ["country", "city"],
        "time_grain_sqla": "P1D",
        "temporal_columns_lookup": {"order_date": True},
        "metrics": ["SUM(sales)"],
        "metricsLayout": "COLUMNS",
        "order_desc": True,
        "aggregateFunction": "Sum",
        "valueFormat": "SMART_NUMBER",
        "date_format": "smart_date",
        "rowOrder": "key_a_to_z",
        "colOrder": "key_a_to_z",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build pivot table params with row/column groupings and metrics.

        Description:
            Maps kwargs keys (groupby_columns, groupby_rows) to internal field names
            (groupbyColumns, groupbyRows) for Superset compatibility.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby_columns, groupby_rows, metrics.

        Returns:
            Complete params dict for pivot_table_v2 chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        # Map snake_case kwargs to camelCase Superset field names
        d["groupbyColumns"] = kwargs.get("groupby_columns", d["groupbyColumns"])
        d["groupbyRows"] = kwargs.get("groupby_rows", d["groupbyRows"])
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  24. Mixed Timeseries  –  mixed_timeseries
# ─────────────────────────────────────────────────────────────────────────────

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
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set primary axis: metrics and groupby
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Set secondary axis: metrics_b and groupby_b for the dual-axis
        d["metrics_b"] = kwargs.get("metrics_b", d["metrics_b"])
        d["groupby_b"] = kwargs.get("groupby_b", d["groupby_b"])
        # Set chart type for primary and secondary axes (line, bar, etc.)
        d["seriesType"] = kwargs.get("seriesType", d["seriesType"])
        d["seriesTypeB"] = kwargs.get("seriesTypeB", d["seriesTypeB"])
        # Set shared time axis fields
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  25. Word Cloud  –  word_cloud
# ─────────────────────────────────────────────────────────────────────────────

class WordCloudStrategy(ChartParamsStrategy):
    """
    Word cloud chart strategy (word_cloud).

    Description:
        Generates params for a word cloud where font size represents metric value
        for each text category. Requires a series column and metric.
    """
    VIZ_TYPE = "word_cloud"
    DEFAULTS = {
        "series": "customer_name",
        "metric": "count",
        "row_limit": 100,
        "size_from": 10,
        "size_to": 70,
        "rotation": "square",
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build word cloud chart params with series column and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The word cloud displays text
            labels from the series column sized proportionally to the metric value.
            Higher metric values produce larger, more prominent labels.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: series, metric.

        Returns:
            Complete params dict for word_cloud chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Set word cloud fields: series (text labels), metric (label size)
        d["series"] = kwargs.get("series", d["series"])
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  26. World Map  –  world_map
# ─────────────────────────────────────────────────────────────────────────────

class WorldMapStrategy(ChartParamsStrategy):
    """
    World map chart strategy (world_map).

    Description:
        Generates params for a choropleth world map showing metric values by geographic region.
        Requires groupby for country/region and metric for color intensity.
    """
    VIZ_TYPE = "world_map"
    DEFAULTS = {
        "groupby": ["country"],
        "metric": "SUM(sales)",
        "color_scheme": "supersetColors",
        "number_format": "SMART_NUMBER",
        "map_title": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """
        Build world map chart params with groupby regions and metric.

        Description:
            Merges DEFAULTS with kwargs overrides. The world map displays metric
            values as color intensity on geographical regions. Groupby defines the
            country/region column, and metric controls choropleth color intensity.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for world_map chart.
        """
        # Start with a shallow copy of the strategy's default parameter values
        d = dict(self.DEFAULTS)
        # Set the actual Superset viz_type string
        d["viz_type"] = self.VIZ_TYPE
        # Normalize groupby to always be a list (country/region column)
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        # Override metric if provided (choropleth color intensity)
        d["metric"] = kwargs.get("metric", d["metric"])
        # Prepend the base dict with datasource reference and row_limit
        base = self._base(datasource_id)
        base.update(d)
        return base


# REMOVED: parallel — chart plugin not registered on Superset 6.1.0 instance.
# #  27. Parallel  –  parallel  (generic fallback strategy)
#
# class ParallelStrategy(ChartParamsStrategy):
#     VIZ_TYPE = "parallel"
#     DEFAULTS = {
#         "groupby": [],
#         "metrics": ["count"],
#         "color_scheme": "supersetColors",
#     }
#
#     def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
#         d = dict(self.DEFAULTS)
#         d["viz_type"] = self.VIZ_TYPE
#         d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
#         d["metrics"] = kwargs.get("metrics", d["metrics"])
#         base = self._base(datasource_id)
#         base.update(d)
#         return base


# ─────────────────────────────────────────────────────────────────────────────
#  Registry  –  maps generic / actual viz_type → strategy class
# ─────────────────────────────────────────────────────────────────────────────

# TYPE_MAP: maps user-friendly chart type names (aliases) to actual Superset
# viz_type strings registered by chart plugins. This allows users to pass
# simplified names like "line" or "bar" and have them resolved automatically.
# Key = user-facing alias (e.g. "line"), Value = actual Superset plugin name
# (e.g. "echarts_timeseries_line").
# Some aliases map multiple user terms to the same viz_type (e.g. "map" and
# "world_map" both resolve to "world_map"; "boxplot" and "box_plot" both
# resolve to "box_plot").
TYPE_MAP: Dict[str, str] = {
    # generic shorthand → actual Superset viz_type
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
    # REMOVED: "parallel": "parallel",  — chart plugin not registered on Superset 6.1.0
}

# _REGISTRY: maps actual Superset viz_type strings to instantiated strategy objects.
# Each entry links a chart plugin name (e.g. "echarts_timeseries_line") to a
# concrete strategy instance that knows how to build its parameter defaults.
# Strategies are instantiated once at module load and reused across all calls.
# Key = actual Superset viz_type string, Value = singleton ChartParamsStrategy instance.
_REGISTRY: Dict[str, ChartParamsStrategy] = {
    "echarts_timeseries_line": LineChartStrategy(),
    "echarts_timeseries_bar": BarChartStrategy(),
    "echarts_area": AreaChartStrategy(),
    "echarts_timeseries_scatter": ScatterChartStrategy(),
    "bubble_v2": BubbleChartStrategy(),
    "pie": PieChartStrategy(),
    "table": TableChartStrategy(),
    "big_number": BigNumberChartStrategy(),
    "big_number_total": BigNumberTotalStrategy(),
    "gauge_chart": GaugeChartStrategy(),
    "gantt_chart": GanttChartStrategy(),
    "box_plot": BoxPlotStrategy(),
    "funnel": FunnelStrategy(),
    "graph_chart": GraphChartStrategy(),
    "waterfall": WaterfallStrategy(),
    "heatmap_v2": HeatmapStrategy(),
    "histogram_v2": HistogramStrategy(),
    "radar": RadarStrategy(),
    "sankey_v2": SankeyStrategy(),
    "sunburst_v2": SunburstStrategy(),
    "treemap_v2": TreeMapStrategy(),
    "tree_chart": TreeStrategy(),
    "pivot_table_v2": PivotTableStrategy(),
    "mixed_timeseries": MixedTimeseriesStrategy(),
    "word_cloud": WordCloudStrategy(),
    "world_map": WorldMapStrategy(),
    # REMOVED: "parallel": ParallelStrategy(),  — chart plugin not registered
}


# ─────────────────────────────────────────────────────────────────────────────
#  Public API  –  backwards compatible wrapper
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
    # Step 1: Resolve user-friendly name (e.g. "line") to actual Superset viz_type (e.g. "echarts_timeseries_line")
    actual_viz = TYPE_MAP.get(viz_type, viz_type)
    # Step 2: Look up the strategy instance for this viz_type
    strategy = _REGISTRY.get(actual_viz)
    if strategy is None:
        # Unknown viz type – return minimal fallback params to prevent crashes
        return {
            "datasource": f"{datasource_id}__table",
            "viz_type": actual_viz,
            "adhoc_filters": [],
            "row_limit": kwargs.get("row_limit", 10000),
            "metric": kwargs.get("metric", "count"),
            "metrics": kwargs.get("metrics", ["count"]),
            "groupby": kwargs.get("groupby", []),
        }
    # Step 3: Delegate to the concrete strategy to build full params
    return strategy.build(datasource_id, **kwargs)
