"""
Spatial chart strategies for Apache Superset.

Contains: WorldMap
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy


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
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base
