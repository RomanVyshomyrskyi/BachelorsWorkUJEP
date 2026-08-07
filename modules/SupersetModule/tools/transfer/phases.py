"""
Dashboard and chart transfer tools between Superset servers.

Phase implementation functions for the 3-phase transfer pipeline.
"""

import json
import time
from typing import Dict, Any, List, Tuple, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_get_resource, impl_list_resources
from modules.SupersetModule.tools.transfer.core import _parse_json_result, NEED_INPUT_PREFIX
from modules.SupersetModule.tools.transfer.table_check import _resolve_dataset
from modules.SupersetModule.tools.transfer.charts import _recreate_chart, _extract_sql_from_params, _extract_fields_from_params, _compute_diff_str
from modules.SupersetModule.tools.transfer.matching import _find_matching_charts_at_destination
from modules.SupersetModule.tools.transfer.helpers import collect_expected_columns


async def _resolve_datasets_phase(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    unique_ds_ids: Dict[int, str],
    parsed_db_mappings: Dict[int, int],
    parsed_table_mappings: Dict[str, str],
    expected_columns_by_ds: Dict[int, List[str]],
    report: Dict[str, Any],
    log,
) -> Tuple[Dict[int, Tuple[int, str]], int]:
    """Execute Phase 1: Resolve and recreate all unique datasources on the target server.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        unique_ds_ids: Dict of source datasource IDs to datasource types.
        parsed_db_mappings: Pre-configured database ID mappings.
        parsed_table_mappings: Pre-configured table name mappings.
        expected_columns_by_ds: Expected columns for each datasource.
        report: Transfer report dict to update.
        log: Logger instance.

    Returns:
        Tuple of (ds_mapping, ds_errors).
    """
    log.info(f"Phase 1: Resolving {len(unique_ds_ids)} unique datasources (reverse hierarchy)...")

    ds_mapping: Dict[int, Tuple[int, str]] = {}
    ds_errors = 0
    for old_ds_id, ds_type in unique_ds_ids.items():
        t0 = time.time()
        new_ds_id, resolved_ds_type, err = await _resolve_dataset(
            manager, source_server_id, target_server_id,
            old_ds_id, parsed_db_mappings, parsed_table_mappings,
            expected_columns=expected_columns_by_ds.get(old_ds_id),
        )
        elapsed = int((time.time() - t0) * 1000)
        entry: Dict[str, Any] = {
            "source_dataset_id": old_ds_id,
            "target_dataset_id": new_ds_id,
            "status": "success" if not err else "failed",
            "duration_ms": elapsed,
        }
        if new_ds_id:
            entry["target_dataset_id"] = new_ds_id
        if err:
            if err.startswith(NEED_INPUT_PREFIX):
                entry["status"] = "need_input"
                entry["error"] = err
                report["execution"]["datasets"].append(entry)
                return ds_mapping, -1, err
            entry["error"] = err
            ds_errors += 1
            report["errors"].append(f"Dataset {old_ds_id}: {err}")
        else:
            ds_mapping[old_ds_id] = (new_ds_id, resolved_ds_type or ds_type)
            log.info(f"  Dataset {old_ds_id} -> {new_ds_id}")
        report["execution"]["datasets"].append(entry)

    return ds_mapping, ds_errors, None


async def _recreate_charts_phase(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    chart_details: List[Dict[str, Any]],
    ds_mapping: Dict[int, Tuple[int, str]],
    report: Dict[str, Any],
    log,
) -> Tuple[Dict[int, int], int]:
    """Execute Phase 2: Recreate all charts on the target server with remapped datasources.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        chart_details: List of chart detail dicts.
        ds_mapping: Mapping of source datasource IDs to target (id, type).
        report: Transfer report dict to update.
        log: Logger instance.

    Returns:
        Tuple of (chart_id_mapping, chart_errors).
    """
    log.info(f"Phase 2: Recreating {len(chart_details)} charts...")

    chart_id_mapping: Dict[int, int] = {}
    chart_errors = 0
    for cd in chart_details:
        cid = cd["id"]
        t0 = time.time()
        new_cid, err = await _recreate_chart(
            manager, source_server_id, target_server_id,
            cid, ds_mapping
        )
        elapsed = int((time.time() - t0) * 1000)
        entry = {
            "source_chart_id": cid,
            "chart_name": cd["slice_name"],
            "target_chart_id": new_cid,
            "status": "success" if not err else "failed",
            "duration_ms": elapsed,
        }
        if err:
            chart_errors += 1
            entry["error"] = err
            report["errors"].append(f"Chart {cid} ('{cd['slice_name']}'): {err}")
        else:
            chart_id_mapping[cid] = new_cid
            log.info(f"  Chart {cid} ('{cd['slice_name']}') -> {new_cid}")
        report["execution"]["charts"].append(entry)

    return chart_id_mapping, chart_errors


async def _create_dashboard_phase(
    manager: ConnectionManager,
    target_server_id: str,
    dashboard_id: int,
    dashboard_title: str,
    chart_id_mapping: Dict[int, int],
    dash_result: Dict[str, Any],
    report: Dict[str, Any],
    log,
) -> Tuple[str, int, int]:
    """Execute Phase 3: Create the target dashboard with remapped position_json.

    Args:
        manager: ConnectionManager instance.
        target_server_id: Target Superset server ID.
        dashboard_id: Source dashboard ID.
        dashboard_title: Dashboard title.
        chart_id_mapping: Mapping of source chart IDs to target chart IDs.
        dash_result: Source dashboard result dict.
        report: Transfer report dict to update.
        log: Logger instance.

    Returns:
        Tuple of (new_dash_str, new_dash_id, dash_elapsed).
    """
    from modules.SupersetModule.tools.transfer.position_json import _remap_chart_ids_in_position_json
    from modules.SupersetModule.tools.dashboards import create_dashboard, bulk_link_charts

    log.info(f"Phase 3: Creating dashboard...")
    t0 = time.time()

    position_json_raw = dash_result.get("position_json", "{}")
    json_metadata_raw = dash_result.get("json_metadata", "{}")
    slug = dash_result.get("slug")
    published = dash_result.get("published", False)

    if isinstance(position_json_raw, dict):
        position_json = position_json_raw
    else:
        try:
            position_json = json.loads(position_json_raw)
        except (json.JSONDecodeError, TypeError):
            position_json = {}

    position_json_updated = json.dumps(_remap_chart_ids_in_position_json(position_json, chart_id_mapping))

    if isinstance(json_metadata_raw, dict):
        json_metadata = json_metadata_raw
    else:
        try:
            json_metadata = json.loads(json_metadata_raw)
        except (json.JSONDecodeError, TypeError):
            json_metadata = {}

    json_metadata_updated = json.dumps(json_metadata)

    new_dash_str = await create_dashboard(
        manager, target_server_id,
        dashboard_title=dashboard_title,
        position_json=position_json_updated,
        slug=slug,
        json_metadata=json_metadata_updated,
        published=published,
        skip_chart_validation=True
    )

    dash_elapsed = int((time.time() - t0) * 1000)
    return new_dash_str, dash_elapsed


def _build_summary(
    dashboard_id: int,
    source_server_id: str,
    target_server_id: str,
    new_dash_id: int,
    ds_mapping: Dict[int, Tuple[int, str]],
    chart_id_mapping: Dict[int, int],
    link_result: Any,
    report: Dict[str, Any],
    mc,
    transfer_start: float,
) -> str:
    """Build and return the final success summary JSON.

    Args:
        dashboard_id: Source dashboard ID.
        source_server_id: Source server ID.
        target_server_id: Target server ID.
        new_dash_id: New dashboard ID on target.
        ds_mapping: Dataset mapping dict.
        chart_id_mapping: Chart mapping dict.
        link_result: Result from bulk_link_charts.
        report: Transfer report dict.
        mc: Metrics collector.
        transfer_start: Transfer start timestamp.

    Returns:
        JSON string summary.
    """
    summary = {
        "message": "Dashboard transferred successfully",
        "source": f"{source_server_id} -> {target_server_id}",
        "source_dashboard_id": dashboard_id,
        "target_dashboard_id": new_dash_id,
        "datasource_mapping": {str(k): v[0] for k, v in ds_mapping.items()},
        "chart_mapping": {str(k): v for k, v in chart_id_mapping.items()},
        "link_result": link_result,
        "_report": report,
    }
    mc.tool_calls.labels(tool="superset_transfer_dashboard", status="success").inc()
    mc.tool_duration.labels(tool="superset_transfer_dashboard").observe(time.monotonic() - transfer_start)
    mc.transfers_total.labels(status="success").inc()
    return json.dumps(summary, indent=2, default=str)
