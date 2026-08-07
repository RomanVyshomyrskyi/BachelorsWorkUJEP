"""
Auto-fix for common chart parameter mistakes.

Provides auto_fix_chart_params() which applies 18+ fix rules to correct
common parameter issues that cause Superset frontend errors.
"""

import logging
from typing import Any, Dict

from .fixer_core import apply_early_fixes
from .fixer_universal import apply_universal_fixes

logger = logging.getLogger(__name__)


def auto_fix_chart_params(viz_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """
    Auto-fix common parameter mistakes in chart params.

    Description:
        Applies a series of corrections to chart params to fix the most common
        issues that cause Superset frontend errors (e.g., 'e.column is undefined',
        'Data error', 'Cannot compile Column object'). Handles metric format
        conversion, groupby normalization, null column replacement, and more.

    Args:
        viz_type: The Superset viz_type string.
        params: Chart params dict with potential issues.

    Returns:
        A new params dict with corrections applied.

    Note:
        Always call validate_chart_params() after this function to check for
        remaining errors that couldn't be auto-fixed.

    Fixes applied (in order):
        Fix 0:  datasource_id type conversion (str -> int)
        Fix 1:  entity field for map types
        Fix 1.5: cycle-breaking hint for Sankey charts
        Fix 2:  Pie/waterfall groupby normalization (list -> string)
        Fix 3:  Pie/waterfall metrics array -> metric object
        Fix 3.1: Singular string metric types: metrics array -> metric string
        Fix 4:  String metrics -> AdHocMetricObject conversion
        Fix 5:  Scatter/bubble axis nesting correction
        Fix 6:  String array type object fix
        Fix 7:  AdHocMetricObject required fields completion
        Fix 8:  AdHoc metrics array fix
        Fix 9:  Mixed metrics type fix
        Fix 11: Universal groupby array normalization
        Fix 12: Big number time config for dashboard rendering
        Fix 13: Universal null column_name replacement
        Fix 13b: Universal orderby cleanup (drop null entries)
        Fix 13c: Columns/all_columns null entry cleanup
        Fix 17: Time series + big_number granularity/time_range defaults
        Fix 14: String metrics -> AdHocMetricObject in arrays
        Fix 14a: Axis fields -> AdHocMetricObject
        Fix 16: Universal aggregate/expressionType/label completion
        Fix 18: Universal label for groupby/orderby/columns dict entries

        Example:
            >>> bad_params = {"groupby": "product_line", "metrics": ["SUM(sales)"], "metric": None}
            >>> fixed = auto_fix_chart_params("echarts_timeseries_line", bad_params)
            >>> fixed["groupby"]
            ['product_line']
            >>> fixed["metric"]
            {'aggregate': 'AVG', 'column': {'column_name': 'count'}, 'expressionType': 'SIMPLE', 'label': 'AVG(count)'}
    """
    # Early fixes: 0-12 (type conversion, entity, groupby, metric conversions)
    fixed = apply_early_fixes(viz_type, params)
    # Universal fixes: 13-18 (null columns, labels, cleanup, completion)
    fixed = apply_universal_fixes(viz_type, fixed)
    return fixed
