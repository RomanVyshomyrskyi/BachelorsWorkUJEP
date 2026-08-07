"""
KPI chart strategies for Apache Superset.

Contains: BigNumber, BigNumberTotal, Gauge
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metric"] = kwargs.get("metric", d["metric"])
        d["x_axis"] = kwargs.get("x_axis", d["x_axis"])
        d["time_grain_sqla"] = kwargs.get("time_grain_sqla", d["time_grain_sqla"])
        d["show_trend_line"] = kwargs.get("show_trend_line", d["show_trend_line"])
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base

