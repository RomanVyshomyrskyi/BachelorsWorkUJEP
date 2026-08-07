"""
Display chart strategies for Apache Superset.

Contains: Gantt, BoxPlot, Graph, Heatmap, Histogram
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["start_time"] = kwargs.get("start_time", d["start_time"])
        d["end_time"] = kwargs.get("end_time", d["end_time"])
        d["y_axis"] = kwargs.get("y_axis", d["y_axis"])
        d["series"] = kwargs.get("series", d["series"])
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["columns"] = kwargs.get("columns", [kwargs.get("column", d["columns"][0])])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        d["temporal_columns_lookup"] = {d["columns"][0]: True}
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        d["layout"] = kwargs.get("layout", d["layout"])
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["groupby"] = kwargs.get("groupby", d["groupby"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        col = kwargs.get("x_axis", kwargs.get("column", d["column"]))
        d["column"] = col
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["bins"] = kwargs.get("bins", d["bins"])
        base = self._base(datasource_id)
        base.update(d)
        return base

