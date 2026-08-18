"""
Table chart strategies for Apache Superset.

Contains: Table, PivotTable
"""
from typing import Any, Dict

from ._base import ChartParamsStrategy

class TableChartStrategy(ChartParamsStrategy):
    """
    Table chart strategy (table).
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
        base = self._base(datasource_id, row_limit=1000)
        base.update(d)
        return base



class PivotTableStrategy(ChartParamsStrategy):
    """
    Pivot table strategy (pivot_table_v2).
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
        d["groupbyColumns"] = kwargs.get("groupby_columns", d["groupbyColumns"])
        d["groupbyRows"] = kwargs.get("groupby_rows", d["groupbyRows"])
        d["metrics"] = kwargs.get("metrics", d["metrics"])
        base = self._base(datasource_id)
        base.update(d)
        return base

