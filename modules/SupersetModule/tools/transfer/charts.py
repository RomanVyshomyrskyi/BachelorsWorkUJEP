"""
Dashboard and chart transfer tools between Superset servers.

Chart recreation and comparison functions.
"""

import json
from typing import Any, Dict, Optional, Tuple, List
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.charts import create_chart
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector

log = LogCollector(__name__)


async def _recreate_chart(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    source_chart_id: int,
    ds_mapping: Dict[int, Tuple[int, str]]
) -> Tuple[Optional[int], Optional[str]]:
    """Clone a source chart onto the target server with remapped datasources.

    Fetches the source chart's full details (name, viz_type, params, description,
    datasource), looks up the target datasource ID from ``ds_mapping``, and
    calls ``create_chart()`` to recreate the chart on the target.
        This is the chart phase of the 3-phase transfer pipeline. Each chart's
        datasource reference is remapped from source datasource ID to target
        datasource ID. Charts referencing untransferred datasources are skipped
        with an error.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        source_chart_id: Source chart ID to clone.
        ds_mapping: Dict mapping source datasource IDs to
            (target_datasource_id, datasource_type) tuples.

    Returns:
        Tuple of (new_chart_id, error_message). On success: (int_id, None).
        On failure: (None, error_string).
    """
    chart_str = await impl_get_resource(manager, source_server_id, "chart", source_chart_id)
    chart_data = _parse_json_result(chart_str)
    if not chart_data:
        return None, f"Could not get chart {source_chart_id} from source: {chart_str}"

    chart_result = chart_data.get("result", {})
    slice_name = chart_result.get("slice_name", f"Chart {source_chart_id}")
    viz_type = chart_result.get("viz_type", "table")
    old_ds_id = chart_result.get("datasource_id")
    datasource_type = chart_result.get("datasource_type", "table")
    params_raw = chart_result.get("params", "{}")
    description = chart_result.get("description")

    if old_ds_id not in ds_mapping:
        return None, f"Chart {source_chart_id} references datasource {old_ds_id} which was not transferred"

    new_ds_id, new_ds_type = ds_mapping[old_ds_id]

    if isinstance(params_raw, dict):
        params_parsed = dict(params_raw)
    else:
        params_parsed = json.loads(params_raw)

    # Remove fields that should be passed separately to the API
    for key in ["datasource_id", "datasource", "datasource_type", "viz_type",
                "time_grain_sqla", "granularity_sqla", "title"]:
        params_parsed.pop(key, None)

    params_json = json.dumps(params_parsed)

    result_str = await create_chart(
        manager,
        target_server_id,
        slice_name=slice_name,
        viz_type=viz_type,
        datasource_id=new_ds_id,
        datasource_type=new_ds_type or datasource_type,
        params=params_json,
        description=description,
        skip_data_test=True
    )

    if "Error" in result_str:
        return None, f"Failed to create chart '{slice_name}' on target: {result_str}"

    result_data = _parse_json_result(result_str)
    if not result_data:
        return None, f"Could not parse chart creation result: {result_str}"

    new_chart_id = result_data.get("id")
    if not new_chart_id:
        return None, f"Chart created but no ID returned: {result_str}"

    return new_chart_id, None


def _extract_sql_from_params(params_raw: Any) -> Optional[str]:
    """Extract an SQL query string from chart params, if present.

    Searches common keys where SQL might be embedded in chart parameters:
    ``sql``, ``query``, ``sql_expression``, ``where``, ``having``, ``filters``.

    Args:
        params_raw: Chart params as a JSON string or dict.

    Returns:
        The first non-empty SQL string found, or None if no SQL is present.
    """
    try:
        p = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
    except (json.JSONDecodeError, TypeError):
        return None
    for key in ("sql", "query", "sql_expression", "where", "having", "filters"):
        val = p.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip()
    return None


def _extract_fields_from_params(params_raw: Any) -> Dict[str, Any]:
    """Extract key chart configuration fields from chart params for diff/comparison.

    Parses the params JSON string or dict and returns a flattened dict of
    relevant fields: metrics, groupby, timeseries_limit, row_limit, order_desc,
    granularity, filters, where, having, x_axis, y_axis, entity.

    Args:
        params_raw: Chart params as a JSON string or dict.

    Returns:
        Dict of extracted field values. Missing fields are absent from the result.
    """
    try:
        p = json.loads(params_raw) if isinstance(params_raw, str) else (params_raw or {})
    except (json.JSONDecodeError, TypeError):
        return {}
    return {
        "metrics": p.get("metric") or (p.get("metrics") or []),
        "groupby": p.get("groupby") or (p.get("groupby") or []),
        "timeseries_limit": p.get("timeseries_limit"),
        "row_limit": p.get("row_limit"),
        "order_desc": p.get("order_desc"),
        "granularity": p.get("granularity") or p.get("time_grain_sqla"),
        "filters": p.get("ad-hoc_filters") or p.get("filters"),
        "where": p.get("where"),
        "having": p.get("having"),
        "x_axis": p.get("x_axis"),
        "y_axis": p.get("y_axis"),
        "entity": p.get("entity"),
    }


def _compute_diff_str(left: Dict[str, Any], right: Dict[str, Any]) -> str:
    """Compute a human-readable diff between two field dicts.

    Compares all keys present in either dict and produces a diff string
    showing which fields differ, with their source and destination values.

    Args:
        left: Source-side field dict to compare.
        right: Destination-side field dict to compare.

    Returns:
        Multi-line diff string or ``"  (identical)"`` if no differences found.
    """
    diff_lines = []
    all_keys = set(left.keys()) | set(right.keys())
    for k in sorted(all_keys):
        lv = left.get(k)
        rv = right.get(k)
        if lv != rv:
            lvs = json.dumps(lv, default=str) if not isinstance(lv, str) else lv
            rvs = json.dumps(rv, default=str) if not isinstance(rv, str) else rv
            diff_lines.append(f"  ~ {k}:")
            diff_lines.append(f"    - source: {lvs}")
            diff_lines.append(f"    + destination: {rvs}")
    return "\n".join(diff_lines) if diff_lines else "  (identical)"
