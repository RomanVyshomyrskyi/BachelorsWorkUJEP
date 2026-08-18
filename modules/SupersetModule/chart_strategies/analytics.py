"""
Analytical chart strategies for Apache Superset.

Contains: Radar, WordCloud
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

class RadarStrategy(ChartParamsStrategy):
    """
    Radar chart strategy (radar).
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
            Merges DEFAULTS with kwargs overrides. The radar/spider chart plots
            multiple metrics on separate axes for each groupby category, allowing
            visual comparison across dimensions.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metrics.

        Returns:
            Complete params dict for radar chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class WordCloudStrategy(ChartParamsStrategy):
    """
    Word cloud chart strategy (word_cloud).
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
            Merges DEFAULTS with kwargs overrides. The word cloud displays text
            labels from the series column sized proportionally to the metric value.
            Higher metric values produce larger, more prominent labels.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: series, metric.

        Returns:
            Complete params dict for word_cloud chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["series"] = kwargs.get("series", d["series"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base