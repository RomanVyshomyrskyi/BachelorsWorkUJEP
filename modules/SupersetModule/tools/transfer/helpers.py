"""
Dashboard and chart transfer tools between Superset servers.

Helper functions for dashboard transfer.
"""

import json
import re
from typing import Any, Dict, List, Optional, Set, Union


def extract_chart_ids_from_position_json(position_json: Any) -> List[int]:
    """Extract chart IDs from a dashboard position_json structure.

    Recursively walks the position_json and finds all chartId/slice_id
    references. If position_json is a string, parses it as JSON first.

    Args:
        position_json: Dashboard position_json as dict, list, or JSON string.

    Returns:
        Sorted list of unique integer chart IDs found.
    """
    if isinstance(position_json, str):
        try:
            pos_data = json.loads(position_json)
        except (json.JSONDecodeError, TypeError):
            return []
    else:
        pos_data = position_json

    found: Set[int] = set()

    def _find(obj: Any) -> Set[int]:
        if isinstance(obj, dict):
            cid = obj.get("chartId") or obj.get("slice_id")
            if cid is not None:
                try:
                    found.add(int(cid))
                except (ValueError, TypeError):
                    pass
            for v in obj.values():
                _find(v)
        elif isinstance(obj, list):
            for item in obj:
                _find(item)
        return found

    _find(pos_data)
    return sorted(found)


def collect_expected_columns(
    chart_details: List[Dict[str, Any]]
) -> Dict[int, List[str]]:
    """Collect expected column names from chart params across all charts.

    Extracts column references from metric expressions, groupby fields,
    x_axis, entity, series, source, and target parameters.

    Args:
        chart_details: List of chart detail dicts, each with a 'params' key.

    Returns:
        Dict mapping datasource ID to list of expected column names.
    """
    expected_columns_by_ds: Dict[int, List[str]] = {}
    for cd in chart_details:
        ds_id = cd["datasource_id"]
        if ds_id:
            if ds_id not in expected_columns_by_ds:
                expected_columns_by_ds[ds_id] = []
            params = cd.get("params", {})
            for field in ["metrics", "groupby"]:
                vals = params.get(field, [])
                if isinstance(vals, list):
                    for v in vals:
                        if isinstance(v, str):
                            m = re.match(
                                r"^(?:SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$",
                                v,
                                re.IGNORECASE,
                            )
                            if m:
                                expected_columns_by_ds[ds_id].append(m.group(1))
                        elif isinstance(v, dict):
                            col = v.get("column", {}).get("column_name", "")
                            if col:
                                expected_columns_by_ds[ds_id].append(col)
            for field in ["x_axis", "entity", "series", "source", "target"]:
                val = params.get(field)
                if isinstance(val, str) and val.strip():
                    expected_columns_by_ds[ds_id].append(val.strip())
    return expected_columns_by_ds
