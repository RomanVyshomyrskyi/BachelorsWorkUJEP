"""
Dashboard and chart transfer tools between Superset servers.

Discovery phase: fetch dashboard metadata, chart details, and compute diffs.
"""

import json
from typing import Dict, Any, List, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_get_resource, impl_list_resources
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.SupersetModule.tools.transfer.charts import _extract_sql_from_params, _extract_fields_from_params, _compute_diff_str
from modules.SupersetModule.tools.transfer.helpers import extract_chart_ids_from_position_json


async def _discover_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    dashboard_id: int,
    report_base: Dict[str, Any],
    log,
) -> Dict[str, Any]:
    """Discover source dashboard metadata, chart details, and compute diffs.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        dashboard_id: Dashboard ID to discover.
        report_base: Base report dict to populate.
        log: Logger instance.

    Returns:
        Dict with report, dash_result, dashboard_title, chart_details,
        source_chart_ids, unique_ds_ids.
    """
    from modules.SupersetModule.tools.transfer.matching import _find_matching_charts_at_destination

    report: Dict[str, Any] = {
        "source": {"server_id": source_server_id, "base_url": ""},
        "destination": {"server_id": "", "base_url": ""},
        "dashboard": {},
        "datasets": [],
        "charts": [],
        "execution": {"datasets": [], "charts": [], "dashboard": {}},
        "success_rate": "",
        "errors": [],
        "diffs": [],
    }
    report["_logs"] = log._logs

    log.info(f"Fetching source dashboard {dashboard_id}...")
    dash_str = await impl_get_resource(manager, source_server_id, "dashboard", dashboard_id)
    dash_data = _parse_json_result(dash_str)
    if not dash_data:
        return f"Could not get dashboard {dashboard_id} from source: {dash_str}"

    dash_result = dash_data.get("result", {})
    dashboard_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")
    source_charts = dash_result.get("charts", [])
    if not source_charts:
        return f"No charts found in dashboard {dashboard_id}"

    position_json = dash_result.get("position_json")
    source_chart_ids = []
    if position_json:
        try:
            source_chart_ids = extract_chart_ids_from_position_json(position_json)
            log.info(f"Extracted {len(source_chart_ids)} chart IDs from position_json: {source_chart_ids}")
        except Exception as e:
            log.info(f"Failed to parse position_json for chart IDs: {e}")

    if not source_chart_ids:
        for c in source_charts:
            if not c:
                continue
            if isinstance(c, dict):
                cid = c.get("id")
            elif isinstance(c, (int, str)):
                cid = c
            else:
                continue
            if cid:
                source_chart_ids.append(int(cid) if isinstance(cid, str) else cid)

    report["dashboard"] = {
        "id": dashboard_id,
        "title": dashboard_title,
        "chart_count": len(source_chart_ids),
        "charts": [],
    }

    log.info(f"Dashboard '{dashboard_title}' ({dashboard_id}) has {len(source_chart_ids)} charts")

    chart_details = []
    for cid in source_chart_ids:
        chart_str = await impl_get_resource(manager, source_server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if not chart_data:
            continue
        cr = chart_data.get("result", {})
        params_raw = cr.get("params", "{}")
        sql = _extract_sql_from_params(params_raw)
        ds_id = cr.get("datasource_id")
        ds_sql = None
        if ds_id:
            ds_sql = await _fetch_chart_sql_from_datasource(manager, source_server_id, ds_id)
        fields = _extract_fields_from_params(params_raw)
        detail = {
            "id": cid,
            "slice_name": cr.get("slice_name", f"Chart {cid}"),
            "viz_type": cr.get("viz_type", "?"),
            "datasource_id": ds_id,
            "datasource_type": cr.get("datasource_type", "table"),
            "params": fields,
            "sql": sql or ds_sql or "(none)",
            "description": cr.get("description"),
        }
        chart_details.append(detail)
        report["dashboard"]["charts"].append(detail)

    unique_ds_ids: Dict[int, str] = {}
    for cd in chart_details:
        ds_id = cd["datasource_id"]
        if ds_id:
            unique_ds_ids[ds_id] = cd["datasource_type"]

    dest_matches = await _find_matching_charts_at_destination(manager, source_server_id, chart_details)
    for cd in chart_details:
        cid = cd["id"]
        if cid in dest_matches:
            dc = dest_matches[cid]
            d_params = _extract_fields_from_params(dc.get("params", "{}"))
            d_viz = dc.get("viz_type", "")
            diff_parts = []
            if d_viz != cd["viz_type"]:
                diff_parts.append(f"  viz_type: {cd['viz_type']} -> {d_viz}")
            param_diff = _compute_diff_str(cd["params"], d_params)
            if param_diff != "  (identical)":
                diff_parts.append(f"  params:\n{param_diff}")
            diff_text = "\n".join(diff_parts) if diff_parts else "  (identical)"
            report["diffs"].append({
                "chart_id": cid,
                "chart_name": cd["slice_name"],
                "source_viz": cd["viz_type"],
                "destination_viz": d_viz,
                "exists_in_destination": True,
                "diff": diff_text,
            })

    return {
        "report": report,
        "dash_result": dash_result,
        "dashboard_title": dashboard_title,
        "chart_details": chart_details,
        "source_chart_ids": source_chart_ids,
        "unique_ds_ids": unique_ds_ids,
    }


async def _fetch_chart_sql_from_datasource(
    manager, source_server_id: str, datasource_id: int
) -> Optional[str]:
    """Retrieve the SQL definition of a chart's underlying datasource."""
    ds_str = await impl_list_resources(manager, source_server_id, "dataset")
    ds_data = _parse_json_result(ds_str)
    if not ds_data:
        return None
    for ds in ds_data.get("result", []):
        if isinstance(ds, dict) and ds.get("id") == datasource_id:
            return ds.get("sql")
    return None
