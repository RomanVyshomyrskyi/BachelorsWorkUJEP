"""
Dashboard and chart transfer tools between Superset servers.

Position JSON remapping for chart ID updates after transfer.
"""

from typing import Dict


def _remap_chart_ids_in_position_json(position_json: Dict, chart_id_mapping: Dict[int, int]) -> Dict:
    """Update position_json chart references with new target chart IDs.

    Recursively walks the dashboard position_json structure and replaces
    chart ID references in CHART-type components. Updates both the ``id``
    field and ``meta.chartId``/``meta.id`` values.

    Description:
        After charts are recreated on the target server, they get new IDs.
        The dashboard's position_json must reference the new IDs so the
        dashboard renders the correct charts. This function performs a deep
        recursive update of all CHART components in the layout tree.

    Args:
        position_json: Dashboard position_json dict with old chart IDs.
        chart_id_mapping: Dict mapping old chart IDs to new chart IDs.

    Returns:
        A new position_json dict (deep copy) with all chart IDs remapped.
        Non-dict inputs are returned unchanged.
    """
    if not isinstance(position_json, dict):
        return position_json

    updated = {}
    for key, value in position_json.items():
        if isinstance(value, dict):
            child_type = value.get("type", "")
            if child_type == "CHART":
                old_chart_id = value.get("meta", {}).get("chartId") or value.get("id")
                if old_chart_id and old_chart_id in chart_id_mapping:
                    new_id = chart_id_mapping[old_chart_id]
                    new_value = dict(value)
                    new_value["id"] = new_id
                    if "meta" in new_value:
                        new_meta = dict(new_value["meta"])
                        new_meta["chartId"] = new_id
                        new_meta["id"] = new_id
                        new_value["meta"] = new_meta
                    updated[key] = new_value
                    continue
            updated[key] = _remap_chart_ids_in_position_json(value, chart_id_mapping)
        elif isinstance(value, list):
            updated[key] = [
                _remap_chart_ids_in_position_json(item, chart_id_mapping) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            updated[key] = value

    return updated
