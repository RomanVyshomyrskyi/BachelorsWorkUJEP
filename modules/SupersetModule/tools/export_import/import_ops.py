"""
Per-dashboard import from JSON.

Reads a per-dashboard JSON export and recreates the dashboard with all its
charts, datasets, and databases on a target Superset server. Follows
dependency order: databases -> datasets -> charts -> dashboard.

All ID references are automatically remapped during import.

MCP Tools Provided:
    - import_dashboard_from_json: Import one dashboard with all charts/datasets/databases
"""

import json
import time
import copy
from typing import Dict, Any, List, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_list_resources
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


async def import_dashboard_from_json(
    manager: ConnectionManager,
    target_server_id: str,
    config_str: str,
    db_mapping: Optional[Dict[str, int]] = None,
    skip_existing: bool = True,
) -> str:
    """Import a dashboard export JSON into a target Superset server.

    Reads a previously exported dashboard transfer JSON and recreates the
    dashboard with all its charts, datasets, and databases on the target
    server. Follows strict dependency order to ensure all references are valid.

    Database mapping: If ``db_mapping`` is provided, source database IDs are
    mapped to existing target database IDs. Without mapping, the tool attempts
    to match databases by name.

    Args:
        manager: ConnectionManager instance.
        target_server_id: The target Superset server ID.
        config_str: Either a file path to the exported JSON file, or raw JSON
            string content from ``export_dashboard_to_json``. For large exports
            with many charts, use a file path to avoid MCP payload limits.
        db_mapping: Optional dict mapping source database ID strings to
            target database IDs (e.g., ``{"1": 5}``). If a source database
            ID is not mapped, it will be matched by name on the target.
        skip_existing: If True, skip resources that already exist on the
            target (matched by name). Defaults to True.

    Returns:
        JSON string with the import report including summary, id_mappings,
        and any errors.
    """
    import os
    mc = get_metrics()
    start_time = time.monotonic()

    ctx = manager.get_context(target_server_id)
    if not ctx:
        return log.collect(f"Error: Server '{target_server_id}' not found.")

    try:
        await ensure_auth(ctx)
    except Exception as e:
        return log.collect(f"Error: Authentication failed: {e}")

    # Load config: if config_str is a file path, read it
    config_content = config_str.strip()

    if not config_content:
        return log.collect("Error: config_str is empty. Provide either a file path or raw JSON content.")

    # Check if it looks like a file path (starts with /, ./, ../, or drive letter)
    is_file_path = (
        config_content.startswith('/') or
        config_content.startswith('./') or
        config_content.startswith('../') or
        (len(config_content) > 1 and config_content[1] == ':') or
        (os.path.exists(config_content) and os.path.isfile(config_content))
    )

    if is_file_path:
        try:
            with open(config_content, 'r', encoding='utf-8') as f:
                config_content = f.read()
            log.info(f"Loaded export config from file: {config_str}")
        except FileNotFoundError:
            return log.collect(f"Error: File not found: {config_str}")
        except PermissionError:
            return log.collect(f"Error: Permission denied reading file: {config_str}")
        except OSError as e:
            return log.collect(f"Error: Could not read file {config_str}: {e}")

    # Parse config
    try:
        config = json.loads(config_content)
    except json.JSONDecodeError as e:
        return log.collect(f"Error: Invalid JSON: {e}")

    resources = config.get("resources", {})
    id_mappings: Dict[str, Dict[int, int]] = {
        "databases": {},
        "datasets": {},
        "charts": {},
    }
    summary: Dict[str, Dict[str, int]] = {
        "databases": {"imported": 0, "skipped": 0, "failed": 0},
        "datasets": {"imported": 0, "skipped": 0, "failed": 0},
        "charts": {"imported": 0, "skipped": 0, "failed": 0},
        "dashboard": {"imported": 0, "skipped": 0, "failed": 0},
    }
    errors: List[str] = []

    # --- Phase 1: Import Databases ---
    db_resources = resources.get("databases", [])
    if db_resources:
        log.info("Phase 1: Importing databases...")
        for db in db_resources:
            db_id = db.get("id")
            db_name = db.get("database_name", f"DB-{db_id}")
            try:
                target_db_id = await _import_database(
                    manager, target_server_id, db,
                    db_mapping, skip_existing,
                )
                if target_db_id:
                    id_mappings["databases"][db_id] = target_db_id
                    summary["databases"]["imported"] += 1
                    log.info(f"  Database '{db_name}' -> target ID {target_db_id}")
                else:
                    summary["databases"]["skipped"] += 1
            except Exception as e:
                summary["databases"]["failed"] += 1
                err_msg = f"Failed to import database '{db_name}': {e}"
                errors.append(err_msg)
                log.error(err_msg)
    else:
        log.info("Phase 1: No databases in export, skipping.")

    # --- Phase 2: Import Datasets ---
    ds_resources = resources.get("datasets", [])
    if ds_resources:
        log.info("Phase 2: Importing datasets...")
        for ds in ds_resources:
            ds_id = ds.get("id")
            ds_name = ds.get("table_name", f"Dataset-{ds_id}")
            try:
                target_ds_id = await _import_dataset(
                    manager, target_server_id, ds,
                    id_mappings["databases"], skip_existing,
                )
                if target_ds_id:
                    id_mappings["datasets"][ds_id] = target_ds_id
                    summary["datasets"]["imported"] += 1
                    log.info(f"  Dataset '{ds_name}' -> target ID {target_ds_id}")
                else:
                    summary["datasets"]["skipped"] += 1
            except Exception as e:
                summary["datasets"]["failed"] += 1
                err_msg = f"Failed to import dataset '{ds_name}': {e}"
                errors.append(err_msg)
                log.error(err_msg)
    else:
        log.info("Phase 2: No datasets in export, skipping.")

    # --- Phase 3: Import Charts ---
    chart_resources = resources.get("charts", [])
    if chart_resources:
        log.info("Phase 3: Importing charts...")
        for ch in chart_resources:
            ch_id = ch.get("id")
            ch_name = ch.get("slice_name", f"Chart-{ch_id}")
            try:
                target_ch_id = await _import_chart(
                    manager, target_server_id, ch,
                    id_mappings["datasets"], skip_existing,
                )
                if target_ch_id:
                    id_mappings["charts"][ch_id] = target_ch_id
                    summary["charts"]["imported"] += 1
                    log.info(f"  Chart '{ch_name}' -> target ID {target_ch_id}")
                else:
                    summary["charts"]["skipped"] += 1
            except Exception as e:
                summary["charts"]["failed"] += 1
                err_msg = f"Failed to import chart '{ch_name}': {e}"
                errors.append(err_msg)
                log.error(err_msg)
    else:
        log.info("Phase 3: No charts in export, skipping.")

    # --- Phase 4: Import Dashboard ---
    dash_resources = resources.get("dashboards", [])
    if dash_resources:
        log.info("Phase 4: Importing dashboard...")
        for dash in dash_resources:
            dash_id = dash.get("id")
            dash_title = dash.get("dashboard_title", f"Dashboard-{dash_id}")
            try:
                target_dash_id = await _import_dashboard(
                    manager, target_server_id, dash,
                    id_mappings["charts"], skip_existing,
                )
                if target_dash_id:
                    summary["dashboard"]["imported"] += 1
                    log.info(f"  Dashboard '{dash_title}' -> target ID {target_dash_id}")
                else:
                    summary["dashboard"]["skipped"] += 1
            except Exception as e:
                summary["dashboard"]["failed"] += 1
                err_msg = f"Failed to import dashboard '{dash_title}': {e}"
                errors.append(err_msg)
                log.error(err_msg)
    else:
        log.info("Phase 4: No dashboards in export, skipping.")

    total_imported = sum(v["imported"] for v in summary.values())
    total_failed = sum(v["failed"] for v in summary.values())

    source_dashboard_id = config.get("source_dashboard_id", "unknown")

    report = {
        "message": f"Import completed: {total_imported} items imported, {total_failed} failed",
        "target_server": target_server_id,
        "source_server": config.get("source_server", "unknown"),
        "source_dashboard_id": source_dashboard_id,
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": summary,
        "id_mappings": {
            resource: {str(k): v for k, v in mappings.items()}
            for resource, mappings in id_mappings.items()
        },
        "errors": errors,
        "import_duration_ms": int((time.monotonic() - start_time) * 1000),
    }

    mc.tool_calls.labels(tool="import_dashboard_from_json", status="success" if total_failed == 0 else "partial").inc()
    mc.tool_duration.labels(tool="import_dashboard_from_json").observe(time.monotonic() - start_time)

    return json.dumps(report, indent=2, default=str)


async def _import_database(
    manager: ConnectionManager,
    server_id: str,
    db: Dict[str, Any],
    db_mapping: Optional[Dict[str, int]],
    skip_existing: bool,
) -> Optional[int]:
    """Import a database: use mapping, match by name, or create."""
    source_db_id = str(db.get("id"))
    db_name = db.get("database_name", "")

    # Check mapping first
    if db_mapping and source_db_id in db_mapping:
        return db_mapping[source_db_id]

    # Check if database with same name already exists on target
    dbs_str = await impl_list_resources(manager, server_id, "database")
    dbs_data = _parse_json_result(dbs_str)
    if dbs_data:
        for existing_db in dbs_data.get("result", []):
            if existing_db.get("database_name", "").lower() == db_name.lower():
                log.info(f"  Database '{db_name}' already exists on target (ID {existing_db['id']})")
                return existing_db["id"]

    # Create database if not found
    log.info(f"  Creating database '{db_name}' on target...")
    return await _create_database_on_target(manager, server_id, db)


async def _create_database_on_target(
    manager: ConnectionManager,
    server_id: str,
    db: Dict[str, Any],
) -> Optional[int]:
    """Create a database on the target server."""
    db_name = db.get("database_name", "Imported DB")
    db_payload = {
        "database_name": db_name,
        "sqlalchemy_uri": db.get("sqlalchemy_uri", ""),
        "engine_name": db.get("engine_name"),
        "extra": db.get("extra", {}),
        "allow_csv_upload": db.get("allow_csv_upload", False),
        "allow_dml": db.get("allow_dml", False),
        "allow_schema_metadata_fetch": db.get("allow_schema_metadata_fetch", True),
        "expose_in_sqllab": db.get("expose_in_sqllab", True),
    }
    db_payload = {k: v for k, v in db_payload.items() if v is not None}

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/database/",
            json_body=json.dumps(db_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create database '{db_name}': {e}")
        return None


async def _import_dataset(
    manager: ConnectionManager,
    server_id: str,
    ds: Dict[str, Any],
    db_id_map: Dict[int, int],
    skip_existing: bool,
) -> Optional[int]:
    """Import a dataset with remapped database reference."""
    old_db_id = ds.get("database")
    if isinstance(old_db_id, dict):
        old_db_id = old_db_id.get("id", old_db_id.get("database"))
    elif isinstance(old_db_id, str):
        try:
            old_db_id = int(old_db_id)
        except (ValueError, TypeError):
            pass

    new_db_id = db_id_map.get(old_db_id)
    if new_db_id is None:
        log.error(f"  Dataset '{ds.get('table_name')}' references database {old_db_id} which was not imported")
        return None

    # Check if dataset already exists on target
    ds_list_str = await impl_list_resources(manager, server_id, "dataset")
    ds_list_data = _parse_json_result(ds_list_str)
    if ds_list_data:
        for existing_ds in ds_list_data.get("result", []):
            if existing_ds.get("table_name") == ds.get("table_name"):
                ds_schema = existing_ds.get("schema", "")
                ds_db = existing_ds.get("database", {})
                if isinstance(ds_db, dict):
                    ds_db_id = ds_db.get("id")
                else:
                    ds_db_id = ds_db
                if ds_schema == ds.get("schema") or (not ds_schema and not ds.get("schema")):
                    if ds_db_id == new_db_id:
                        log.info(f"  Dataset '{ds.get('table_name')}' already exists (ID {existing_ds['id']})")
                        return existing_ds["id"]

    # Check if dataset already exists with old ID in export
    if skip_existing and ds.get("id") and ds["id"] in db_id_map.values():
        log.info(f"  Dataset with source ID {ds.get('id')} already exists")
        return ds["id"]

    # Create dataset
    if ds.get("sql"):
        log.info(f"  Creating virtual dataset '{ds.get('table_name')}'...")
        return await _create_virtual_dataset(manager, server_id, ds, new_db_id)
    else:
        log.info(f"  Creating physical dataset '{ds.get('table_name')}'...")
        return await _create_physical_dataset(manager, server_id, ds, new_db_id)


async def _create_physical_dataset(
    manager: ConnectionManager,
    server_id: str,
    ds: Dict[str, Any],
    database_id: int,
) -> Optional[int]:
    """Create a physical dataset on target."""
    ds_payload = {
        "table_name": ds.get("table_name", ""),
        "database": database_id,
    }
    if ds.get("schema"):
        ds_payload["schema"] = ds["schema"]
    if ds.get("description"):
        ds_payload["description"] = ds["description"]
    if ds.get("columns"):
        ds_payload["columns"] = ds["columns"]
    if ds.get("metrics"):
        ds_payload["metrics"] = ds["metrics"]
    if ds.get("sql_expression"):
        ds_payload["sql_expression"] = ds["sql_expression"]

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/dataset/",
            json_body=json.dumps(ds_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create physical dataset '{ds.get('table_name')}': {e}")
        return None


async def _create_virtual_dataset(
    manager: ConnectionManager,
    server_id: str,
    ds: Dict[str, Any],
    database_id: int,
) -> Optional[int]:
    """Create a virtual dataset on target."""
    ds_payload = {
        "table_name": ds.get("table_name", ""),
        "database": database_id,
        "sql": ds.get("sql", ""),
    }
    if ds.get("schema"):
        ds_payload["schema"] = ds["schema"]
    if ds.get("description"):
        ds_payload["description"] = ds["description"]
    if ds.get("columns"):
        ds_payload["columns"] = ds["columns"]
    if ds.get("metrics"):
        ds_payload["metrics"] = ds["metrics"]

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/dataset/",
            json_body=json.dumps(ds_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create virtual dataset '{ds.get('table_name')}': {e}")
        return None


async def _import_chart(
    manager: ConnectionManager,
    server_id: str,
    chart: Dict[str, Any],
    ds_id_map: Dict[int, int],
    skip_existing: bool,
) -> Optional[int]:
    """Import a chart with remapped datasource reference and full params."""
    old_ds_id = chart.get("datasource_id")
    if isinstance(old_ds_id, str):
        try:
            old_ds_id = int(old_ds_id)
        except (ValueError, TypeError):
            pass

    new_ds_id = ds_id_map.get(old_ds_id)
    if new_ds_id is None:
        log.error(f"  Chart '{chart.get('slice_name')}' references dataset {old_ds_id} which was not imported")
        return None

    datasource_type = chart.get("datasource_type", "table")

    # Parse params and remap datasource reference
    params_raw = chart.get("params", "{}")
    if isinstance(params_raw, str):
        try:
            params = json.loads(params_raw)
        except json.JSONDecodeError:
            params = {}
    else:
        params = params_raw or {}

    # Remap datasource in params
    params["datasource_id"] = new_ds_id
    params["datasource"] = f"{new_ds_id}__{datasource_type}"
    params["datasource_type"] = datasource_type

    # Remove source chart id from params
    params.pop("id", None)

    params_json = json.dumps(params)

    # Check if chart already exists by name
    if skip_existing:
        charts_str = await impl_list_resources(manager, server_id, "chart")
        charts_data = _parse_json_result(charts_str)
        if charts_data:
            for existing_ch in charts_data.get("result", []):
                if existing_ch.get("slice_name") == chart.get("slice_name"):
                    log.info(f"  Chart '{chart.get('slice_name')}' already exists (ID {existing_ch['id']})")
                    return existing_ch["id"]

    # Create chart via API
    chart_payload = {
        "slice_name": chart.get("slice_name", f"Imported Chart"),
        "viz_type": chart.get("viz_type", "table"),
        "datasource_id": new_ds_id,
        "datasource_type": datasource_type,
        "params": params_json,
    }
    if chart.get("description"):
        chart_payload["description"] = chart["description"]

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/chart/",
            json_body=json.dumps(chart_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create chart '{chart.get('slice_name')}': {e}")
        return None


async def _import_dashboard(
    manager: ConnectionManager,
    server_id: str,
    dashboard: Dict[str, Any],
    chart_id_map: Dict[int, int],
    skip_existing: bool,
) -> Optional[int]:
    """Import dashboard with remapped chart references in position_json."""
    dash_title = dashboard.get("dashboard_title", f"Imported Dashboard")

    # Remap position_json chart IDs
    position_json_raw = dashboard.get("position_json", "{}")
    if isinstance(position_json_raw, dict):
        position_json = position_json_raw
    else:
        try:
            position_json = json.loads(position_json_raw)
        except (json.JSONDecodeError, TypeError):
            position_json = {}

    position_json_updated = _remap_chart_ids_in_position_json(position_json, chart_id_map)

    # Remap json_metadata
    json_metadata_raw = dashboard.get("json_metadata", "{}")
    if isinstance(json_metadata_raw, dict):
        json_metadata = json_metadata_raw
    else:
        try:
            json_metadata = json.loads(json_metadata_raw)
        except (json.JSONDecodeError, TypeError):
            json_metadata = {}

    # Check if dashboard already exists by name
    if skip_existing:
        dashboards_str = await impl_list_resources(manager, server_id, "dashboard")
        dashboards_data = _parse_json_result(dashboards_str)
        if dashboards_data:
            for existing_dash in dashboards_data.get("result", []):
                if existing_dash.get("dashboard_title") == dash_title:
                    log.info(f"  Dashboard '{dash_title}' already exists (ID {existing_dash['id']})")
                    return existing_dash["id"]

    # Create dashboard via API
    dash_payload = {
        "dashboard_title": dash_title,
        "position_json": json.dumps(position_json_updated),
        "slug": dashboard.get("slug"),
        "json_metadata": json.dumps(json_metadata) if json_metadata else None,
        "published": dashboard.get("published", False),
        "owners": dashboard.get("owners", []),
        "roles": dashboard.get("roles", []),
    }
    dash_payload = {k: v for k, v in dash_payload.items() if v is not None}

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/dashboard/",
            json_body=json.dumps(dash_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create dashboard '{dash_title}': {e}")
        return None


def _remap_chart_ids_in_position_json(
    position_json: Dict[str, Any],
    chart_id_map: Dict[int, int],
) -> Dict[str, Any]:
    """Recursively remap chart IDs in position_json."""
    result = copy.deepcopy(position_json)

    def _remap(obj: Any) -> Any:
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                if key in ("chartId", "slice_id", "id"):
                    if isinstance(value, (int, str)):
                        old_id = int(value)
                        if old_id in chart_id_map:
                            new_dict[key] = chart_id_map[old_id]
                        else:
                            new_dict[key] = value
                            log.warning(f"  Chart ID {old_id} not in chart_id_map, keeping original")
                    else:
                        new_dict[key] = _remap(value)
                elif key == "meta" and isinstance(value, dict):
                    new_dict[key] = _remap(value)
                else:
                    new_dict[key] = _remap(value)
            return new_dict
        elif isinstance(obj, list):
            return [_remap(item) for item in obj]
        return obj

    return _remap(result)
