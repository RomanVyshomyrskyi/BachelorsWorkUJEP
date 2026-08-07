"""
Dashboard and chart transfer tools between Superset servers.

Chart matching functions for comparing source and destination charts.
"""

from typing import Any, Dict, List, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_list_resources
from modules.SupersetModule.tools.transfer.core import _parse_json_result


async def _fetch_chart_sql_from_datasource(
    manager, source_server_id: str, datasource_id: int
) -> Optional[str]:
    """Retrieve the SQL definition of a chart's underlying datasource.

    Fetches the dataset detail for the given datasource_id and returns the
    ``sql`` field if it is a non-empty string (virtual datasets have SQL;
    physical tables typically have ``None`` or empty ``sql``).

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        datasource_id: Dataset/datasource ID to fetch.

    Returns:
        SQL string if the datasource has one, or None if it doesn't or the
        fetch fails.
    """
    ds_str = await impl_list_resources(manager, source_server_id, "dataset")
    ds_data = _parse_json_result(ds_str)
    if not ds_data:
        return None
    for ds in ds_data.get("result", []):
        if isinstance(ds, dict) and ds.get("id") == datasource_id:
            return ds.get("sql")
    return None


async def _find_matching_charts_at_destination(
    manager, target_server_id: str, source_charts: List[Dict[str, Any]]
) -> Dict[int, Dict[str, Any]]:
    """Find charts on the destination server that match source charts by name.

    Lists all charts on the target server and matches them against the source
    chart list using case-insensitive ``slice_name`` comparison. Used to
    detect pre-existing charts that may have been transferred previously.

    Args:
        manager: ConnectionManager instance.
        target_server_id: Target Superset server ID.
        source_charts: List of source chart dicts with ``id`` and ``slice_name`` keys.

    Returns:
        Dict mapping source chart ID -> destination chart detail dict.
    """
    dlist_str = await impl_list_resources(manager, target_server_id, "chart")
    dlist_data = _parse_json_result(dlist_str)
    if not dlist_data:
        return {}
    dest_charts = dlist_data.get("result", [])
    if not isinstance(dest_charts, list):
        return {}
    matches = {}
    for sc in source_charts:
        sname = (sc.get("slice_name") or "").strip().lower()
        if not sname:
            continue
        for dc in dest_charts:
            dname = (dc.get("slice_name") or "").strip().lower()
            if dname == sname:
                matches[sc["id"]] = dc
                break
    return matches
