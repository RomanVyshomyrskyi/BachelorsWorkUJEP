"""
Validate and fix metric column names against actual dataset columns.

Description:
    Prevents "Metric 'MAX(col)' does not exist" errors by ensuring chart params
    use column names that match the dataset's actual columns in Superset.
    Supports resolving metric strings, AdHocMetricObjects, groupby columns,
    x_axis fields, and scatter/bubble axis values.

Column Name Resolution Pipeline:
    The resolution process flows through several stages:
    1. **Metric parsing** (`parse_metric_string`): Extracts aggregate function and
       column name from strings like 'SUM(sales)', 'sum__revenue', or bare 'count'.
    2. **Column lookup** (`resolve_column_name`): Performs case-insensitive matching
       (by default) of requested column names against the dataset's actual columns,
       returning the correctly-cased column from the dataset.
    3. **Metric resolution** (`resolve_metrics`): Recursively processes string metrics,
       AdHocMetricObject dicts, or lists of metrics, correcting column names at each
       nesting level.
    4. **Groupby resolution** (`resolve_groupby`): Corrects column case in groupby
       fields (string or list).
    5. **Orchestrator** (`resolve_chart_params`): The main entry point that dispatches
       all metric-related fields (metric, metrics, groupby, x_axis, scatter axes)
       through the resolver pipeline and collects all warnings.

    The pipeline is additive-only — invalid columns are warned about but never removed,
    preserving the caller's original intent while correcting what can be fixed.

Usage:
    resolved_params, warnings = resolve_chart_params(params, dataset_columns)
    # resolved_params has all column names corrected to match the dataset
"""

import json
import re
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


def build_adhoc_metric(column_name: str, aggregate: str = "AVG") -> Dict[str, Any]:
    """
    Build an AdHocMetricObject for Superset.

    Description:
        Creates a properly structured metric object dict that Superset's chart API
        expects. Includes aggregate function, nested column reference, expression type,
        and auto-generated label.

    Args:
        column_name: The database column name to aggregate (e.g. "sales").
        aggregate: Aggregation function. One of: SUM, AVG, MIN, MAX, COUNT, COUNT_DISTINCT.

    Returns:
        Dict formatted as an AdHocMetricObject with keys: aggregate, column, expressionType, label.
    """
    # Step 1: Build the metric object with required Superset fields:
    #   - aggregate: the aggregation function (SUM, AVG, etc.)
    #   - column: nested dict with column_name for the database column reference
    #   - expressionType: "SIMPLE" for direct column aggregates
    #   - label: auto-generated human-readable label used by the frontend
    return {
        "aggregate": aggregate,
        "column": {"column_name": column_name},
        "expressionType": "SIMPLE",
        "label": f"{aggregate}({column_name})",
    }


def build_adhoc_dimension(column_name: str) -> Dict[str, Any]:
    """
    Build an AdHocDimensionObject for Superset.

    Description:
        Creates a dimension object dict used for axis values in scatter, bubble,
        and other chart types that accept column references as dimensions.

    Args:
        column_name: The database column name for the dimension.

    Returns:
        Dict formatted as an AdHocDimensionObject with keys: column, expressionType.
    """
    # Step 1: Build the dimension object — similar to AdHocMetricObject but
    #   uses expressionType "DIMENSION" (not "SIMPLE") to signal it's a
    #   grouping/dimensional column rather than an aggregated metric.
    return {
        "column": {"column_name": column_name},
        "expressionType": "DIMENSION",
    }


def parse_metric_string(metric_str: str) -> Tuple[str, str]:
    """
    Parse a metric string like 'SUM(sales)' or 'sum__sales' into (aggregate, column_name).

    Description:
        Extracts the aggregation function and column name from various metric string formats.
        Handles SQL expressions, SQL-style double-underscore format, and bare 'count'.

    Args:
        metric_str: Metric string in one of these formats:
            - SQL expression: 'SUM(sales)', 'AVG(price)', 'COUNT(id)'
            - SQL-style: 'sum__sales', 'avg__count', 'max__value'
            - Simple: 'count' (returns COUNT, "count")

    Returns:
        Tuple of (aggregate, column_name) where aggregate is uppercase (e.g. "SUM", "AVG").

    Example:
        >>> parse_metric_string("SUM(sales)")
        ('SUM', 'sales')
        >>> parse_metric_string("sum__revenue")
        ('SUM', 'revenue')
        >>> parse_metric_string("count")
        ('COUNT', 'count')
    """
    metric_str = metric_str.strip()
    metric_lower = metric_str.lower()

    # Step 1: Handle 'count' as a special case — it's a built-in Superset metric, not a column reference.
    #   Returning ("COUNT", "count") prevents the resolver from trying to find a "count" column.
    if metric_lower == "count":
        return ("COUNT", "count")

    # Step 2: Handle SQL expression format: SUM(column), AVG(column), etc.
    #   The regex captures the aggregate function name and the column inside parentheses,
    #   with tolerance for optional whitespace around the parentheses.
    match = re.match(
        r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2).strip())

    # Step 3: Handle SQL-style metric names: sum__sales, avg__count, max__value
    #   This double-underscore format is used as a safe alternative when parentheses
    #   are problematic (e.g., in URL encoding or certain API payloads).
    match = re.match(
        r"^(sum|avg|min|max|count|count_distinct)__(.+)$",
        metric_str,
        re.IGNORECASE,
    )
    if match:
        return (match.group(1).upper(), match.group(2))

    # Step 4: Fallback — treat entire string as column name with AVG aggregation.
    #   This handles bare column names like "sales" that are passed without an explicit
    #   aggregate function, defaulting to average.
    return ("AVG", metric_str)


def resolve_column_name(
    requested_column: str,
    dataset_columns: List[Dict[str, Any]],
    case_sensitive: bool = False,
) -> Optional[str]:
    """
    Find the actual column name in the dataset that matches the requested name.

    Description:
        Performs exact or case-insensitive matching of a requested column name against
        the actual columns available in a Superset dataset. Returns the actual column
        name from the dataset, or None if no match is found.

    Args:
        requested_column: The column name requested in the chart params (e.g. "Sales").
        dataset_columns: List of column dicts from the dataset, each containing a 'column_name' key.
        case_sensitive: If False (default), performs case-insensitive matching. If True, requires exact match.

    Returns:
        The actual column name from the dataset if found, None if not found,
        or requested_column if dataset_columns is empty (no comparison possible).

    Example:
        >>> resolve_column_name("sales", [{"column_name": "Sales"}, {"column_name": "quantity"}])
        'Sales'
        >>> resolve_column_name("Sales", [{"column_name": "sales"}], case_sensitive=True)
        None
    """
    if not dataset_columns:
        return requested_column  # No columns to check against, return original

    if case_sensitive:
        # Step 1: Case-sensitive — find exact match by iterating through all columns.
        #   This is used when column name casing is known to be reliable.
        for col in dataset_columns:
            if col.get("column_name") == requested_column:
                return col.get("column_name")
        return None
    else:
        # Step 2: Case-insensitive — compare lowercased names for lenient matching.
        #   This is the default mode because Superset datasets often have case variations
        #   (e.g., "Sales" in dataset vs "sales" in user-supplied params).
        #   Returns the ORIGINAL casing from the dataset, not the user's casing.
        requested_lower = requested_column.lower()
        for col in dataset_columns:
            if col.get("column_name", "").lower() == requested_lower:
                return col.get("column_name")
        return None


def resolve_metrics(
    metrics: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve metric column names against actual dataset columns.

    Description:
        Recursively processes metrics in various formats (string, dict, list) and
        corrects column names to match the dataset's actual column names.
        Collects warnings for any columns that were renamed or not found.

    Args:
        metrics: Metric to resolve. Can be:
            - str: A metric string like "SUM(sales)"
            - dict: An AdHocMetricObject with nested column structure
            - list: A list of any of the above
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_metrics, list_of_warnings) where:
            - resolved_metrics: The metrics with corrected column names
            - list_of_warnings: Human-readable warnings about changes made

    Example:
        >>> resolve_metrics("SUM(sales)", [{"column_name": "Sales"}])
        ('SUM(Sales)', ["Metric column 'sales' renamed to 'Sales' to match dataset"])
    """
    warnings = []

    if isinstance(metrics, str):
        # Step 1: Single string metric — parse the aggregate/column pattern and resolve.
        #   Example: "SUM(sales)" → "SUM(Sales)" if the dataset has column "Sales".
        resolved = _resolve_single_metric(metrics, dataset_columns, warnings)
        return resolved, warnings

    if isinstance(metrics, dict):
        # Step 2: AdHocMetricObject — resolve the nested column_name inside column dict.
        #   These objects have structure: {"aggregate": "SUM", "column": {"column_name": "sales"}}
        #   Only the column_name is resolved; aggregate and expressionType are left intact.
        if "column" in metrics and isinstance(metrics["column"], dict):
            col_name = metrics["column"].get("column_name", "")
            actual = resolve_column_name(col_name, dataset_columns)
            if actual != col_name:
                # Column name differs — update to the dataset's actual column name
                metrics["column"]["column_name"] = actual
                warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
            elif actual is None:
                warnings.append(f"Metric column '{col_name}' not found in dataset")
        return metrics, warnings

    if isinstance(metrics, list):
        # Step 3: List of metrics — recursively resolve each element, collecting warnings.
        #   Each element can itself be a string, dict, or nested list.
        resolved_list = []
        for m in metrics:
            resolved_m, warns = resolve_metrics(m, dataset_columns)
            resolved_list.append(resolved_m)
            warnings.extend(warns)
        return resolved_list, warnings

    # Step 4: Unknown type — return unchanged (no resolution possible).
    return metrics, warnings


def _resolve_single_metric(
    metric_str: str,
    dataset_columns: List[Dict[str, Any]],
    warnings: List[str],
) -> str:
    """
    Resolve a single string metric against dataset columns.

    Description:
        Internal helper that parses a string metric, resolves the column name to
        the actual dataset column, and returns the corrected metric string.
        Special-cases bare 'count' to prevent converting it to 'COUNT(count)'.

    Args:
        metric_str: Metric string like "SUM(sales)" or "sum__revenue".
        dataset_columns: List of column dicts from the dataset.
        warnings: Mutable list to append warning messages to.

    Returns:
        The resolved metric string with corrected column name, or original if not found.

    Note:
        Bare 'count' is a built-in Superset metric, not a column reference.
        It is never converted to 'COUNT(count)' regardless of dataset columns.
    """
    # Step 1: Guard against bare 'count' — it's a built-in Superset metric, not a column reference.
    #   Never convert it to 'COUNT(count)' regardless of dataset columns.
    #   Superset treats bare "count" as SQL COUNT(*), not a column aggregation.
    if metric_str.strip().lower() == "count":
        return metric_str

    # Step 2: Parse the metric string to extract aggregate function and column name.
    #   "SUM(sales)" → agg="SUM", col_name="sales"
    #   "sum__revenue" → agg="SUM", col_name="revenue"
    agg, col_name = parse_metric_string(metric_str)

    # Step 3: Resolve the column name to the actual dataset column (case-insensitive).
    #   Returns the dataset's actual column name casing, e.g., "Sales" for "sales".
    actual = resolve_column_name(col_name, dataset_columns)

    if actual is None:
        # Step 4a: Column not found in dataset — warn but keep original string.
        #   We don't remove or replace it because the caller may have valid reasons
        #   (e.g., the column is a computed expression, not a physical column).
        warnings.append(f"Metric column '{col_name}' not found in dataset")
        return metric_str
    elif actual != col_name:
        # Step 4b: Column name differs in casing — rebuild metric with corrected name.
        #   "SUM(sales)" + dataset has "Sales" → "SUM(Sales)"
        warnings.append(f"Metric column '{col_name}' renamed to '{actual}' to match dataset")
        return f"{agg}({actual})"
    elif metric_str != f"{agg}({col_name})":
        # Step 4c: Same column, but metric format differs (e.g., sum__sales → SUM(sales)).
        #   Normalize the format to the standard SQL expression form.
        warnings.append(f"Metric '{metric_str}' converted to '{agg}({col_name})' for Superset")
        return f"{agg}({col_name})"

    # Step 5: Already correct — no changes needed.
    return metric_str


def resolve_groupby(
    groupby: Any,
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Any, List[str]]:
    """
    Resolve groupby column names against actual dataset columns.

    Description:
        Recursively processes groupby column names (string or list) and corrects
        them to match the dataset's actual column names. Collects warnings for
        renamed or missing columns.

    Args:
        groupby: Groupby value — either a single column name string or list of strings.
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_groupby, list_of_warnings).

    Example:
        >>> resolve_groupby("product_line", [{"column_name": "Product_Line"}])
        ('Product_Line', ["Groupby column 'product_line' renamed to 'Product_Line' to match dataset"])
    """
    warnings = []

    if isinstance(groupby, str):
        # Step 1: Single string groupby — resolve column name casing against the dataset.
        #   Example: "product_line" → "Product_Line" if the dataset has that column.
        actual = resolve_column_name(groupby, dataset_columns)
        if actual is None:
            # Column not found — warn but keep original (may be a valid expression)
            warnings.append(f"Groupby column '{groupby}' not found in dataset")
            return groupby, warnings
        elif actual != groupby:
            # Casing differs — update to dataset's actual column name
            warnings.append(f"Groupby column '{groupby}' renamed to '{actual}' to match dataset")
        return actual, warnings

    if isinstance(groupby, list):
        # Step 2: List of groupby columns — recursively resolve each element.
        #   Each item may be a string column name or could be a nested structure.
        resolved_list = []
        for col in groupby:
            resolved_col, warns = resolve_groupby(col, dataset_columns)
            resolved_list.append(resolved_col)
            warnings.extend(warns)
        return resolved_list, warnings

    # Step 3: Unknown type — return unchanged.
    return groupby, warnings


def resolve_chart_params(
    params: Dict[str, Any],
    dataset_columns: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], List[str]]:
    """
    Resolve all metric and groupby column names in chart params.

    Description:
        Master resolver that processes all metric-related fields in a chart params dict:
        'metric' (singular), 'metrics' (plural array), 'groupby', 'x_axis', and
        scatter/bubble axis fields (x, y, size, size_metric, series).
        Corrects all column names to match the dataset and collects warnings.

    Args:
        params: Chart params dict that may contain any of the following keys:
            'metric', 'metrics', 'groupby', 'x_axis', 'x', 'y', 'size', 'size_metric', 'series'.
        dataset_columns: List of column dicts from the dataset for reference.

    Returns:
        Tuple of (resolved_params, list_of_warnings) where:
            - resolved_params: A copy of params with all column names corrected
            - list_of_warnings: Human-readable warnings about all changes made

    Example:
        >>> params = {"metric": "SUM(sales)", "groupby": "product_line"}
        >>> resolved, warns = resolve_chart_params(params, [{"column_name": "Sales"}])
        >>> resolved["metric"]
        'SUM(Sales)'
    """
    warnings = []
    resolved = dict(params)  # Shallow copy to avoid mutating the original

    # ── Phase 1: Resolve 'metric' (singular) ──
    #   Process single metric value — can be a string like "SUM(sales)" or an
    #   AdHocMetricObject dict. Logs the before/after state for debugging.
    if "metric" in resolved:
        before = json.dumps(resolved["metric"], default=str)[:300]
        resolved["metric"], warns = resolve_metrics(resolved["metric"], dataset_columns)
        after = json.dumps(resolved["metric"], default=str)[:300]
        if before != after or warns:
            logger.info("Singular metric resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)

    # ── Phase 2: Resolve 'metrics' (plural array) ──
    #   Process array of metrics — each element can be a string, dict, or nested list.
    #   This covers the primary metrics field for timeseries, bubble, etc.
    if "metrics" in resolved:
        before = json.dumps(resolved["metrics"], default=str)[:500]
        resolved["metrics"], warns = resolve_metrics(resolved["metrics"], dataset_columns)
        after = json.dumps(resolved["metrics"], default=str)[:500]
        if before != after or warns:
            logger.info("Metrics resolved: before=%s after=%s warnings=%s", before, after, warns)
        warnings.extend(warns)

    # ── Phase 3: Resolve 'groupby' ──
    #   Process groupby column name(s) — correct casing for all dimension columns.
    #   Groupby values serve as category/label dimensions on the chart.
    if "groupby" in resolved:
        resolved["groupby"], warns = resolve_groupby(resolved["groupby"], dataset_columns)
        warnings.extend(warns)

    # ── Phase 4: Resolve 'x_axis' for time series charts ──
    #   The x_axis field in time series specifies the temporal column.
    #   Only correct column name casing — do NOT convert to aggregate formulas.
    if "x_axis" in resolved and isinstance(resolved["x_axis"], str):
        actual = resolve_column_name(resolved["x_axis"], dataset_columns)
        if actual is None:
            warnings.append(f"X-axis column '{resolved['x_axis']}' not found in dataset")
        elif actual != resolved["x_axis"]:
            warnings.append(f"X-axis column '{resolved['x_axis']}' renamed to '{actual}' to match dataset")
            resolved["x_axis"] = actual

    # ── Phase 5: Resolve axis values for scatter/bubble charts ──
    #   These chart types use structured axis fields (x, y, size, etc.) that can
    #   contain either plain column names or aggregate formulas.
    #   Two branches:
    #     a) Formula strings like "SUM(sales)" → resolve column name inside the formula
    #     b) Plain column names like "sales" → just fix casing, don't wrap in aggregate
    #   Ad-hoc formulas like 'SUM(sales)' get converted by auto_fix_chart_params
    #   in superset_validation.py; here we only fix naming, not structure.
    for axis in ["x", "y", "size", "size_metric", "series"]:
        if axis in resolved and isinstance(resolved[axis], str):
            if re.match(r"^(SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(.+\)$", resolved[axis], re.IGNORECASE):
                # Branch a: Formula string — parse the aggregate and column, resolve casing
                agg, col_name = parse_metric_string(resolved[axis])
                actual = resolve_column_name(col_name, dataset_columns)
                if actual is None:
                    warnings.append(f"{axis}-axis metric column '{col_name}' not found in dataset")
                elif actual != col_name:
                    warnings.append(f"{axis}-axis column '{col_name}' renamed to '{actual}'")
                    resolved[axis] = f"{agg}({actual})"
            else:
                # Branch b: Plain column name — just resolve casing
                actual = resolve_column_name(resolved[axis], dataset_columns)
                if actual is None:
                    warnings.append(f"{axis}-axis column '{resolved[axis]}' not found in dataset")
                elif actual != resolved[axis]:
                    warnings.append(f"{axis}-axis column '{resolved[axis]}' renamed to '{actual}'")
                    resolved[axis] = actual

    return resolved, warnings
