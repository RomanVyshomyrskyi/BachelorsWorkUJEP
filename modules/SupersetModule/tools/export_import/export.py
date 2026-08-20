"""
Per-dashboard export to JSON.

Exports ONE dashboard with ALL its charts (full params, datasource info),
datasets (columns, metrics, SQL for virtual datasets), and databases into
a single JSON structure suitable for transfer to another Superset instance.

MCP Tools Provided:
    - export_dashboard_to_json: Export one dashboard with all charts/datasets/databases
"""

import json
import time
from typing import Dict, Any, List, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth
from modules.SupersetModule.tools.resources import impl_list_resources, impl_get_resource
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


async def export_dashboard_to_json(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int,
) -> str:
    """Export a single dashboard with ALL its charts, datasets, and databases to JSON.

    Fetches the dashboard metadata, all charts (with full params, viz_type, datasource
    references), all datasets (columns, metrics, SQL for virtual datasets), and all
    databases (connection configs) into a single JSON structure. The export preserves
    the complete layout (position_json) so the dashboard can be recreated with
    identical chart placement on another server.

    Args:
        manager: ConnectionManager instance.
        server_id: The Superset server ID to export from.
        dashboard_id: The ID of the dashboard to export.

    Returns:
        JSON string with the complete dashboard export including metadata,
        dashboards (single entry), charts, datasets, databases, and a summary.
    """
    mc = get_metrics()
    start_time = time.monotonic()

    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(f"Error: Server '{server_id}' not found.")

    try:
        await ensure_auth(ctx)
    except Exception as e:
        return log.collect(f"Error: Authentication failed: {e}")

    export_data: Dict[str, Any] = {
        "export_type": "dashboard_transfer",
        "export_version": "2.0",
        "source_server": server_id,
        "source_dashboard_id": dashboard_id,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resources": {
            "dashboards": [],
            "charts": [],
            "datasets": [],
            "databases": [],
        },
        "summary": {},
        "errors": [],
    }

    # --- Fetch dashboard ---
    log.info(f"Fetching dashboard {dashboard_id} from {server_id}...")
    dash_str = await impl_get_resource(manager, server_id, "dashboard", dashboard_id)
    dash_data = _parse_json_result(dash_str)
    if not dash_data:
        err = f"Could not get dashboard {dashboard_id} from {server_id}: {dash_str}"
        export_data["errors"].append(err)
        _finalize_export(export_data, start_time)
        return json.dumps(export_data, indent=2, default=str)

    dash_result = dash_data.get("result", {})
    dashboard_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")

    # Extract chart IDs from position_json
    position_json_raw = dash_result.get("position_json", "{}")
    chart_ids = _extract_chart_ids_from_position_json(position_json_raw)

    # Also check the charts list from dashboard metadata
    if not chart_ids:
        source_charts = dash_result.get("charts", [])
        for c in source_charts:
            if isinstance(c, dict):
                cid = c.get("id")
            elif isinstance(c, (int, str)):
                cid = c
            else:
                continue
            if cid:
                chart_ids.append(int(cid) if isinstance(cid, str) else cid)

    log.info(f"Dashboard '{dashboard_title}' ({dashboard_id}) has {len(chart_ids)} charts")

    # --- Build dashboard export entry (sanitized) ---
    dashboard_export = _sanitize_resource(dash_result, [
        "id", "created_by", "changed_by", "created_on", "changed_on", "uuid"
    ])
    export_data["resources"]["dashboards"].append(dashboard_export)

    # --- Fetch each chart ---
    chart_details: List[Dict[str, Any]] = []
    unique_ds_ids: Dict[int, str] = {}

    for cid in chart_ids:
        log.info(f"  Fetching chart {cid}...")
        chart_str = await impl_get_resource(manager, server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if not chart_data:
            export_data["errors"].append(f"Could not get chart {cid}: {chart_str}")
            continue

        chart_result = chart_data.get("result", {})
        chart_export = _sanitize_resource(chart_result, [
            "id", "created_by", "changed_by", "created_on", "changed_on", "uuid"
        ])
        export_data["resources"]["charts"].append(chart_export)
        chart_details.append(chart_export)

        ds_id = chart_result.get("datasource_id")
        if ds_id:
            ds_type = chart_result.get("datasource_type", "table")
            unique_ds_ids[int(ds_id)] = ds_type

    # --- Fetch each dataset ---
    for ds_id, ds_type in unique_ds_ids.items():
        log.info(f"  Fetching dataset {ds_id}...")
        ds_str = await impl_get_resource(manager, server_id, "dataset", ds_id)
        ds_data = _parse_json_result(ds_str)
        if not ds_data:
            export_data["errors"].append(f"Could not get dataset {ds_id}: {ds_str}")
            continue

        ds_result = ds_data.get("result", {})
        ds_export = _sanitize_resource(ds_result, [
            "id", "created_by", "changed_by", "created_on", "changed_on", "uuid"
        ])
        export_data["resources"]["datasets"].append(ds_export)

        db_id = ds_result.get("database")
        if isinstance(db_id, dict):
            db_id = db_id.get("id")
        if db_id:
            export_data.setdefault("_pending_dbs", set()).add(int(db_id))

    # --- Fetch each database ---
    if "_pending_dbs" in export_data:
        for db_id in export_data["_pending_dbs"]:
            log.info(f"  Fetching database {db_id}...")
            db_str = await impl_get_resource(manager, server_id, "database", db_id)
            db_data = _parse_json_result(db_str)
            if not db_data:
                export_data["errors"].append(f"Could not get database {db_id}: {db_str}")
                continue

            db_result = db_data.get("result", {})
            db_export = _sanitize_resource(db_result, [
                "id", "created_by", "changed_by", "created_on", "changed_on", "uuid"
            ])
            export_data["resources"]["databases"].append(db_export)

    # Clean up internal key
    export_data.pop("_pending_dbs", None)

    # --- Summary ---
    export_data["summary"] = {
        "dashboard_id": dashboard_id,
        "dashboard_title": dashboard_title,
        "chart_count": len(chart_details),
        "dataset_count": len(export_data["resources"]["datasets"]),
        "database_count": len(export_data["resources"]["databases"]),
        "chart_ids": chart_ids,
        "dataset_ids": [ds.get("id") for ds in export_data["resources"]["datasets"]],
        "database_ids": [db.get("id") for db in export_data["resources"]["databases"]],
    }

    _finalize_export(export_data, start_time)
    return json.dumps(export_data, indent=2, default=str)


def _extract_chart_ids_from_position_json(position_json: Any) -> List[int]:
    """Extract chart IDs from position_json (chartId or slice_id in meta/id)."""
    if isinstance(position_json, str):
        try:
            pos_data = json.loads(position_json)
        except (json.JSONDecodeError, TypeError):
            return []
    else:
        pos_data = position_json

    found: set = set()

    def _find(obj: Any) -> None:
        if isinstance(obj, dict):
            cid = obj.get("chartId") or obj.get("slice_id")
            if cid is not None:
                try:
                    found.add(int(cid))
                except (ValueError, TypeError):
                    pass
            # Also check meta.chartId or meta.id
            meta = obj.get("meta", {})
            if isinstance(meta, dict):
                mid = meta.get("chartId") or meta.get("id")
                if mid is not None:
                    try:
                        found.add(int(mid))
                    except (ValueError, TypeError):
                        pass
            for v in obj.values():
                _find(v)
        elif isinstance(obj, list):
            for item in obj:
                _find(item)

    _find(pos_data)
    return sorted(found)


def _sanitize_resource(resource: Dict[str, Any], fields_to_remove: List[str]) -> Dict[str, Any]:
    """Remove read-only fields from a resource dict."""
    return {k: v for k, v in resource.items() if k not in fields_to_remove}


def _finalize_export(export_data: Dict[str, Any], start_time: float) -> None:
    """Add timing and totals to export data."""
    export_data["total_items"] = sum([
        len(export_data["resources"]["dashboards"]),
        len(export_data["resources"]["charts"]),
        len(export_data["resources"]["datasets"]),
        len(export_data["resources"]["databases"]),
    ])
    export_data["export_duration_ms"] = int((time.monotonic() - start_time) * 1000)
