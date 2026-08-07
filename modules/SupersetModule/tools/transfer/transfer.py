"""
Dashboard and chart transfer tools between Superset servers.

Main dashboard transfer orchestration.
"""

import json
import time
from typing import Dict, Any, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth
from modules.SupersetModule.tools.transfer.core import _parse_json_result, NEED_INPUT_PREFIX
from modules.SupersetModule.tools.transfer.helpers import collect_expected_columns
from modules.SupersetModule.tools.transfer.discovery import _discover_dashboard
from modules.SupersetModule.tools.transfer.phases import (
    _resolve_datasets_phase,
    _recreate_charts_phase,
    _create_dashboard_phase,
    _build_summary,
)
from modules.SupersetModule.exceptions import TransferError
from modules.log_utils import LogCollector
from modules.metrics import get_metrics


async def transfer_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int,
    db_mappings: Optional[str] = None,
    table_mappings: Optional[str] = None
) -> str:
    """Transfer a dashboard and all its charts between Superset servers (3-phase).

    Implements the full dashboard transfer pipeline:

    1. **Discovery**: Fetches the source dashboard metadata and all chart details
       (including SQL, params, datasources, and viz_types).
    2. **Datasets Phase**: Resolves and recreates all unique datasources on the
       target server. Supports both physical tables (checked via information_schema)
       and virtual datasets (recreated with original SQL). May return ``NEED_INPUT``
       if database or table mappings are missing.
    3. **Charts Phase**: Recreates each chart on the target server with remapped
       datasource references. Skips charts whose datasources couldn't be resolved.
    4. **Dashboard Phase**: Creates the target dashboard with remapped
       ``position_json`` (chart IDs updated to target values), then bulk-links
       all recreated charts.

    Description:
        Generates a comprehensive transfer report including source/destination
        metadata, per-item execution status with timing, diffs against existing
        destination charts, error details, and a percentage success rate.
        Reports Prometheus metrics for monitoring.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        dashboard_id: Dashboard ID to transfer from the source.
        db_mappings: Optional JSON string of source->target database ID mappings
            (e.g. ``'{"1": 2, "3": 4}'``).
        table_mappings: Optional JSON string of source->target table name mappings
            (e.g. ``'{"old_table": "new_table"}'``).

    Returns:
        JSON string with either a ``NEED_INPUT:`` message (if user input is
            required for resolution) or a complete transfer summary including
            datasource mapping, chart mapping, and a nested execution report.

    Example:
        result = await transfer_dashboard(
            manager, source_server_id="source", target_server_id="target",
            dashboard_id=789, db_mappings='{"1": 2}', table_mappings='{"old": "new"}'
        )
        # Returns JSON with transfer results including datasource/chart mappings and dashboard ID.
    """
    source_ctx = manager.get_context(source_server_id)
    target_ctx = manager.get_context(target_server_id)

    if not source_ctx or not target_ctx:
        return "Error: Source or target server not found."

    mc = get_metrics()
    transfer_start = time.monotonic()
    log = LogCollector(__name__)

    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)
    except Exception as e:
        return log.collect(TransferError(f"Authentication failed: {e}", details=str(e)).to_json())

    parsed_db_mappings: Dict[int, int] = {}
    if db_mappings:
        try:
            raw = json.loads(db_mappings)
            parsed_db_mappings = {int(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError) as e:
            return log.collect(TransferError("Invalid db_mappings JSON", details=str(e)).to_json())

    parsed_table_mappings: Dict[str, str] = {}
    if table_mappings:
        try:
            parsed_table_mappings = json.loads(table_mappings)
        except json.JSONDecodeError as e:
            return log.collect(TransferError("Invalid table_mappings JSON", details=str(e)).to_json())

    # Phase 0: Discover source dashboard, charts, and compute diffs
    discovery = await _discover_dashboard(
        manager, source_server_id, dashboard_id, report_base={}, log=log,
    )
    if isinstance(discovery, str):
        return discovery

    report = discovery["report"]
    dash_result = discovery["dash_result"]
    dashboard_title = discovery["dashboard_title"]
    chart_details = discovery["chart_details"]
    source_chart_ids = discovery["source_chart_ids"]
    unique_ds_ids = discovery["unique_ds_ids"]

    if not unique_ds_ids:
        report["errors"].append("No datasources found in source charts")
        return json.dumps(report, indent=2, default=str)

    log.info(f"Dashboard requires {len(unique_ds_ids)} unique datasets")

    # Phase 1: Resolve datasets
    expected_columns_by_ds = collect_expected_columns(chart_details)
    ds_mapping, ds_errors, need_input_err = await _resolve_datasets_phase(
        manager, source_server_id, target_server_id,
        unique_ds_ids, parsed_db_mappings, parsed_table_mappings,
        expected_columns_by_ds, report, log,
    )
    if need_input_err:
        return need_input_err
    if ds_errors > 0:
        report["success_rate"] = f"0% — dataset resolution failed"
        return json.dumps(report, indent=2, default=str)

    # Phase 2: Recreate charts
    chart_id_mapping, chart_errors = await _recreate_charts_phase(
        manager, source_server_id, target_server_id,
        chart_details, ds_mapping, report, log,
    )
    if chart_errors > 0:
        report["success_rate"] = f"0% — chart recreation failed"
        return json.dumps(report, indent=2, default=str)

    # Phase 3: Create dashboard
    new_dash_str, dash_elapsed = await _create_dashboard_phase(
        manager, target_server_id, dashboard_id, dashboard_title,
        chart_id_mapping, dash_result, report, log,
    )

    if "Error" in new_dash_str:
        report["execution"]["dashboard"] = {
            "source_id": dashboard_id,
            "status": "failed",
            "error": new_dash_str,
            "duration_ms": dash_elapsed,
        }
        report["errors"].append(f"Dashboard creation failed: {new_dash_str}")
        report["success_rate"] = f"chart: {len(source_chart_ids) - chart_errors}/{len(source_chart_ids)} succeeded, dashboard: failed"
        return json.dumps(report, indent=2, default=str)

    new_dash_data = _parse_json_result(new_dash_str)
    if not new_dash_data:
        return f"Could not parse dashboard creation result: {new_dash_str}"

    new_dash_id = new_dash_data.get("id")
    if not new_dash_id:
        return f"Dashboard created but no ID returned: {new_dash_str}"

    new_chart_ids = list(chart_id_mapping.values())
    link_result = await bulk_link_charts(manager, target_server_id, new_dash_id, new_chart_ids)

    report["execution"]["dashboard"] = {
        "source_id": dashboard_id,
        "target_id": new_dash_id,
        "title": dashboard_title,
        "status": "success",
        "duration_ms": dash_elapsed,
    }

    total_items = len(unique_ds_ids) + len(source_chart_ids) + 1
    total_ok = (len(unique_ds_ids) - ds_errors) + (len(source_chart_ids) - chart_errors) + (1 if "Error" not in str(new_dash_str) else 0)
    pct = round(total_ok / total_items * 100) if total_items else 0
    report["success_rate"] = f"{pct}% ({total_ok}/{total_items} items succeeded)"
    report["total_duration_ms"] = int((time.time() - transfer_start) * 1000)

    return _build_summary(
        dashboard_id, source_server_id, target_server_id,
        new_dash_id, ds_mapping, chart_id_mapping,
        link_result, report, mc, transfer_start,
    )
