import json
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# Base strategy – every chart type follows the exact same interface
# ─────────────────────────────────────────────────────────────────────────────

class ChartParamsStrategy(ABC):
    """Base strategy – every chart type must implement `build()`."""

    VIZ_TYPE: str = ""
    DEFAULTS: Dict[str, Any] = {}
    REQUIRED: List[str] = []

    @abstractmethod
    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        """Return a fully-formed params dict for the Superset chart API."""
        ...

    # ── helpers ─────────────────────────────────────────────────────────────

    @staticmethod
    def _base(datasource_id: int, row_limit: int = 10000) -> Dict[str, Any]:
        """Common base keys all strategies start from."""
        return {
            "datasource": f"{datasource_id}__table",
            "adhoc_filters": [],
            "row_limit": row_limit,
        }

    @staticmethod
    def _normalize_groupby(val: Any) -> List[str]:
        """Ensure groupby is always a list (or empty list)."""
        if isinstance(val, list):
            return val
        if isinstance(val, str):
            return [val]
        return []

    @staticmethod
    def _defaults() -> Dict[str, Any]:
        """Merge strategy defaults – overrideable by kwargs."""
        return dict(ChartParamsStrategy.__subclasses__()[0].DEFAULTS) if ChartParamsStrategy.__subclasses__() else {}


# ─────────────────────────────────────────────────────────────────────────────
#  1.  Line  –  echarts_timeseries_line
# ─────────────────────────────────────────────────────────────────────────────

class LineChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  2.  Bar  –  echarts_timeseries_bar
# ─────────────────────────────────────────────────────────────────────────────

class BarChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  3.  Area  –  echarts_area
# ─────────────────────────────────────────────────────────────────────────────

class AreaChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  4.  Scatter  –  echarts_timeseries_scatter
# ─────────────────────────────────────────────────────────────────────────────

class ScatterChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  5.  Bubble  –  bubble_v2
# ─────────────────────────────────────────────────────────────────────────────

class BubbleChartStrategy(ChartParamsStrategy):
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


# ─────────────────────────────────────────────────────────────────────────────
#  6.  Pie  –  pie
# ─────────────────────────────────────────────────────────────────────────────

class PieChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  7.  Table  –  table
# ─────────────────────────────────────────────────────────────────────────────

class TableChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["all_columns"] = kwargs.get("all_columns", d["all_columns"])
        d["order_by_cols"] = kwargs.get("order_by_cols", d["order_by_cols"])
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  8.  Big Number  –  big_number (with trend line)
# ─────────────────────────────────────────────────────────────────────────────

class BigNumberChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metric"] = kwargs.get("metric", d["metric"])
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        d["show_trend_line"] = kwargs.get("show_trend_line", d["show_trend_line"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  9.  Big Number Total  –  big_number_total
# ─────────────────────────────────────────────────────────────────────────────

class BigNumberTotalStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  10. Gauge  –  gauge_chart
# ─────────────────────────────────────────────────────────────────────────────

class GaugeChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  11. Gantt  –  gantt_chart
# ─────────────────────────────────────────────────────────────────────────────

class GanttChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["start_time"] = kwargs.get("start_time", d["start_time"])
        d["end_time"] = kwargs.get("end_time", d["end_time"])
        d["y_axis"] = kwargs.get("y_axis", d["y_axis"])
        d["series"] = kwargs.get("series", d["series"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  12. Box Plot  –  box_plot
# ─────────────────────────────────────────────────────────────────────────────

class BoxPlotStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["columns"] = kwargs.get("columns", [kwargs.get("column", d["columns"][0])])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["temporal_columns_lookup"] = {d["columns"][0]: True}
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  13. Funnel  –  funnel
# ─────────────────────────────────────────────────────────────────────────────

class FunnelStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  14. Graph  –  graph_chart
# ─────────────────────────────────────────────────────────────────────────────

class GraphChartStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        d["layout"] = kwargs.get("layout", d["layout"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  15. Waterfall  –  waterfall
# ─────────────────────────────────────────────────────────────────────────────

class WaterfallStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  16. Heatmap  –  heatmap_v2
# ─────────────────────────────────────────────────────────────────────────────

class HeatmapStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["groupby"] = kwargs.get("groupby", d["groupby"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  17. Histogram  –  histogram_v2
# ─────────────────────────────────────────────────────────────────────────────

class HistogramStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["column"] = kwargs.get("column", d["column"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["bins"] = kwargs.get("bins", d["bins"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  18. Radar  –  radar
# ─────────────────────────────────────────────────────────────────────────────

class RadarStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  19. Sankey  –  sankey_v2
# ─────────────────────────────────────────────────────────────────────────────

class SankeyStrategy(ChartParamsStrategy):
    VIZ_TYPE = "sankey_v2"
    DEFAULTS = {
        "source": "product_line",
        "target": "deal_size",
        "metric": "count",
        "color_scheme": "supersetColors",
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  20. Sunburst  –  sunburst_v2
# ─────────────────────────────────────────────────────────────────────────────

class SunburstStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["columns"] = kwargs.get("columns", d["columns"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  21. TreeMap  –  treemap_v2
# ─────────────────────────────────────────────────────────────────────────────

class TreeMapStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  22. Tree  –  tree_chart
# ─────────────────────────────────────────────────────────────────────────────

class TreeStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["id"] = kwargs.get("id", d["id"])
        d["parent"] = kwargs.get("parent", d["parent"])
        d["name"] = kwargs.get("name", d["name"])
        d["metric"] = kwargs.get("metric", d["metric"])
        d["layout"] = kwargs.get("layout", d["layout"])
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  23. Pivot Table  –  pivot_table_v2
# ─────────────────────────────────────────────────────────────────────────────

class PivotTableStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
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


# ─────────────────────────────────────────────────────────────────────────────
#  25. Word Cloud  –  word_cloud
# ─────────────────────────────────────────────────────────────────────────────

class WordCloudStrategy(ChartParamsStrategy):
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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["series"] = kwargs.get("series", d["series"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


# ─────────────────────────────────────────────────────────────────────────────
#  26. World Map  –  world_map
# ─────────────────────────────────────────────────────────────────────────────

class WorldMapStrategy(ChartParamsStrategy):
    VIZ_TYPE = "world_map"
    DEFAULTS = {
        "groupby": ["country"],
        "metric": "SUM(sales)",
        "color_scheme": "supersetColors",
        "number_format": "SMART_NUMBER",
        "map_title": True,
    }

    def build(self, datasource_id: int, **kwargs) -> Dict[str, Any]:
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
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

TYPE_MAP: Dict[str, str] = {
    # generic → actual_viz_type
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

    Usage:
        params = get_standard_chart_params("line", 13,
            x_axis="order_date",
            time_grain_sqla="P1M",
            metrics=["SUM(sales)"],
            groupby=["product_line"])
        # Returns: {"datasource": "13__table", "viz_type": "echarts_timeseries_line", ...}

        params_json = json.dumps(params)   # for Superset API
    """
    actual_viz = TYPE_MAP.get(viz_type, viz_type)
    strategy = _REGISTRY.get(actual_viz)
    if strategy is None:
        # Unknown viz type – minimal fallback
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
