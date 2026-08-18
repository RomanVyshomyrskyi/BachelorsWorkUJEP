"""
Hierarchical chart strategies for Apache Superset.

Contains: TreeMap, Sunburst, Sankey, Tree
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

class TreeMapStrategy(ChartParamsStrategy):
    """
    TreeMap chart strategy (treemap_v2).
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
            Merges DEFAULTS with kwargs overrides. The treemap shows hierarchical
            data as nested rectangles, with groupby defining the hierarchy levels
            and metric sizing each rectangle.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: groupby, metric.

        Returns:
            Complete params dict for treemap_v2 chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["groupby"] = self._normalize_groupby(kwargs.get("groupby", d["groupby"]))
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class SunburstStrategy(ChartParamsStrategy):
    """
    Sunburst chart strategy (sunburst_v2).
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
            Merges DEFAULTS with kwargs overrides. The sunburst chart displays
            hierarchical data as concentric rings. The columns field defines the
            hierarchy levels (outer to inner), and the metric sizes each segment.

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: columns (hierarchy levels), metric.

        Returns:
            Complete params dict for sunburst_v2 chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["columns"] = kwargs.get("columns", d["columns"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class SankeyStrategy(ChartParamsStrategy):
    """
    Sankey diagram strategy (sankey_v2).
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
            Merges DEFAULTS with kwargs overrides. The Sankey diagram shows flow
            between source and target nodes, with the metric representing flow
            magnitude (visualized as link width).

        Args:
            datasource_id: Superset datasource/table ID.
            **kwargs: Optional overrides: source, target, metric.

        Returns:
            Complete params dict for sankey_v2 chart.
        """
        d = dict(self.DEFAULTS)
        d["viz_type"] = self.VIZ_TYPE
        d["source"] = kwargs.get("source", d["source"])
        d["target"] = kwargs.get("target", d["target"])
        d["metric"] = kwargs.get("metric", d["metric"])
        base = self._base(datasource_id)
        base.update(d)
        return base


class TreeStrategy(ChartParamsStrategy):
    """
    Tree chart strategy (tree_chart).
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
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base
