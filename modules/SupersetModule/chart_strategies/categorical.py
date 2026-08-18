"""
Categorical chart strategies for Apache Superset.

Contains: Pie, Funnel, Waterfall, Treemap, Sunburst, Sankey, Tree
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy



"""
Categorical chart strategies for Apache Superset.

Contains: Pie, Funnel, Waterfall, Treemap, Sunburst, Sankey, Tree
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy


class PieChartStrategy(ChartParamsStrategy):
    """
    Pie chart strategy (pie).
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
            Merges DEFAULTS with kwargs overrides for groupby (slice categories)
            and metric (slice sizes), sets viz_type and datasource, then returns
            the complete params dict ready for Superset API.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for pie chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class FunnelStrategy(ChartParamsStrategy):
    """
    Funnel chart strategy (funnel).
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
            Merges DEFAULTS with kwargs overrides. The funnel chart shows
            sequential stages (from groupby categories) sized by metric values,
            illustrating process flow and drop-off between stages.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for funnel chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class WaterfallStrategy(ChartParamsStrategy):
    """
    Waterfall chart strategy (waterfall).
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
            Sets x_axis for time dimension, time_grain_sqla for aggregation level,
            optional groupby for series, and metric for values.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: x_axis, time_grain_sqla, groupby, metric.

        Returns:
            Complete params dict for waterfall chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base
