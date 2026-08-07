"""
Base strategy class and shared helpers for chart parameter generation.

All concrete chart strategies inherit from ChartParamsStrategy to get
access to the _base(), _normalize_groupby(), and _defaults() helpers.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List


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
            return val
        if isinstance(val, str):
            return [val]
        return []

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
