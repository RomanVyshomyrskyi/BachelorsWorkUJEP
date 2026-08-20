"""
Import Superset resources from exported JSON into a target server.

This module provides functionality to import dashboards, charts, datasets,
databases, CSS templates, and annotations from an exported JSON structure
into a target Superset server. It handles ID remapping automatically to
ensure all references (chart datasources, dashboard chart links, etc.)
are correctly updated.

The import follows a dependency order:
  1. Databases (created first, referenced by datasets)
  2. Datasets (referenced by charts)
  3. Charts (referenced by dashboards)
  4. Dashboards (created last, linked to charts)

CSS templates and annotations are imported in parallel with their respective phases.

MCP Tools Provided:
    - import_superset_config: Import all resources from JSON into a target server
"""

import json
import time
import re
from typing import Dict, Any, List, Optional, Tuple
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth, execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_list_resources, impl_get_resource
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


async def import_superset_config(
    manager: ConnectionManager,
    target_server_id: str,
    config_json: str,
    db_mappings: Optional[Dict[str, int]] = None,
    create_missing_databases: bool = False,
    skip_existing: bool = True,
) -> str:
    """Import all Superset resources from an exported JSON configuration into a target server.

    Reads a previously exported Superset configuration (JSON string or file content)
    and recreates all resources on the target server. The import follows strict
    dependency ordering to ensure references are valid:
      1. Databases are created first (with optional ID mapping)
      2. Datasets are created with remapped database references
      3. Charts are created with remapped datasource references
      4. Dashboards are created with remapped chart ID references

    Database mapping: If ``db_mappings`` is provided, source database IDs are mapped
    to existing target database IDs. Without mapping, databases are created with
    the same configuration (requiring ``create_missing_databases=True`` or pre-existing
    databases with matching names).

    Args:
        manager: ConnectionManager instance with Superset connection details.
        target_server_id: The ID of the target Superset server to import into.
        config_json: JSON string containing the exported configuration from
            ``export_superset_config``. Must include a "resources" object with
            "databases", "datasets", "charts", and/or "dashboards" keys.
        db_mappings: Optional dict mapping source database ID strings to target
            database IDs (e.g., ``{"1": 5, "2": 7}``). If a source database
            ID is not mapped and the database doesn't exist on target, it will
            be skipped unless ``create_missing_databases=True``.
        create_missing_databases: If True and a source database is not found in
            db_mappings, attempt to create it on the target server.
        skip_existing: If True, skip databases that already exist on the target
            server (matched by name). Defaults to True.

    Returns:
        JSON string containing the import report with:
        - summary: counts of imported/skipped/failed items by type
        - id_mappings: dict mapping source IDs to new target IDs
        - errors: list of error messages for failed items
        - duration_ms: total import duration

    Examples:
        result = await import_superset_config(
            manager, "production", config_json,
            db_mappings={"1": 3, "2": 5}
        )
        # Returns JSON with import report showing what was created/mapped
    """
    mc = get_metrics()
    start_time = time.monotonic()

    ctx = manager.get_context(target_server_id)
    if not ctx:
        return log.collect(f"Error: Server '{target_server_id}' not found.")

    try:
        await ensure_auth(ctx)
    except Exception as e:
        return log.collect(f"Error: Authentication failed: {e}")

    # Parse config
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return log.collect(f"Error: Invalid JSON in config: {e}")

    if "resources" not in config:
        return log.collect("Error: Config must contain a 'resources' object.")

    resources = config["resources"]
    id_mappings: Dict[str, Dict[int, int]] = {
        "databases": {},
        "datasets": {},
        "charts": {},
        "dashboards": {},
    }
    summary: Dict[str, Dict[str, int]] = {
        "databases": {"imported": 0, "skipped": 0, "failed": 0},
        "datasets": {"imported": 0, "skipped": 0, "failed": 0},
        "charts": {"imported": 0, "skipped": 0, "failed": 0},
        "dashboards": {"imported": 0, "skipped": 0, "failed": 0},
        "css_templates": {"imported": 0, "skipped": 0, "failed": 0},
        "annotations": {"imported": 0, "skipped": 0, "failed": 0},
    }
    errors: List[str] = []

    # --- Phase 1: Import Databases ---
    if "databases" in resources:
        log.info("Phase 1: Importing databases...")
        for db in resources["databases"]:
            db_id = db.get("id")
            db_name = db.get("database_name", f"DB-{db_id}")
            try:
                target_db_id = await _import_database(
                    manager, target_server_id, db, db_mappings,
                    create_missing_databases, skip_existing,
                )
                if target_db_id:
                    id_mappings["databases"][db_id] = target_db_id
                    summary["databases"]["imported"] += 1
                    log.info(f"  Database '{db_name}' -> target ID {target_db_id}")
                else:
                    summary["databases"]["skipped"] += 1
                    log.info(f"  Database '{db_name}' skipped (already exists or not imported)")
            except Exception as e:
                summary["databases"]["failed"] += 1
                err_msg = f"Failed to import database '{db_name}': {e}"
                errors.append(err_msg)
                log.error(err_msg)

    # --- Phase 2: Import Datasets ---
    if "datasets" in resources:
        log.info("Phase 2: Importing datasets...")
        for ds in resources["datasets"]:
            ds_id = ds.get("id")
            ds_name = ds.get("table_name", f"Dataset-{ds_id}")
            try:
                target_ds_id = await _import_dataset(
                    manager, target_server_id, ds, id_mappings["databases"],
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

    # --- Phase 3: Import Charts ---
    if "charts" in resources:
        log.info("Phase 3: Importing charts...")
        for ch in resources["charts"]:
            ch_id = ch.get("id")
            ch_name = ch.get("slice_name", f"Chart-{ch_id}")
            try:
                target_ch_id = await _import_chart(
                    manager, target_server_id, ch, id_mappings["datasets"],
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

    # --- Phase 4: Import Dashboards ---
    if "dashboards" in resources:
        log.info("Phase 4: Importing dashboards...")
        for dash in resources["dashboards"]:
            dash_id = dash.get("id")
            dash_title = dash.get("dashboard_title", f"Dashboard-{dash_id}")
            try:
                target_dash_id = await _import_dashboard(
                    manager, target_server_id, dash, id_mappings["charts"],
                )
                if target_dash_id:
                    id_mappings["dashboards"][dash_id] = target_dash_id
                    summary["dashboards"]["imported"] += 1
                    log.info(f"  Dashboard '{dash_title}' -> target ID {target_dash_id}")
                else:
                    summary["dashboards"]["skipped"] += 1
            except Exception as e:
                summary["dashboards"]["failed"] += 1
                err_msg = f"Failed to import dashboard '{dash_title}': {e}"
                errors.append(err_msg)
                log.error(err_msg)

    # --- Phase 5: Import CSS Templates ---
    if "css_templates" in resources:
        log.info("Phase 5: Importing CSS templates...")
        for css in resources["css_templates"]:
            css_id = css.get("id", "unknown")
            css_name = css.get("css_template", f"CSS-{css_id}")[:40]
            try:
                target_css_id = await _import_css_template(
                    manager, target_server_id, css,
                )
                if target_css_id:
                    summary["css_templates"]["imported"] += 1
                else:
                    summary["css_templates"]["skipped"] += 1
            except Exception as e:
                summary["css_templates"]["failed"] += 1
                errors.append(f"Failed to import CSS template '{css_name}': {e}")
                log.error(f"Failed to import CSS template '{css_name}': {e}")

    # --- Phase 6: Import Annotations ---
    if "annotations" in resources:
        log.info("Phase 6: Importing annotation layers...")
        for ann in resources["annotations"]:
            ann_id = ann.get("id", "unknown")
            ann_name = ann.get("name", f"Annotation-{ann_id}")
            try:
                await _import_annotation(manager, target_server_id, ann)
                summary["annotations"]["imported"] += 1
            except Exception as e:
                summary["annotations"]["failed"] += 1
                errors.append(f"Failed to import annotation '{ann_name}': {e}")
                log.error(f"Failed to import annotation '{ann_name}': {e}")

    total_imported = sum(v["imported"] for v in summary.values())
    total_failed = sum(v["failed"] for v in summary.values())

    report = {
        "message": f"Import completed: {total_imported} items imported, {total_failed} failed",
        "target_server": target_server_id,
        "source_version": config.get("export_version", "unknown"),
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "summary": summary,
        "id_mappings": {
            resource: {str(k): v for k, v in mappings.items()}
            for resource, mappings in id_mappings.items()
        },
        "errors": errors,
        "total_items": total_imported + total_failed,
        "import_duration_ms": int((time.monotonic() - start_time) * 1000),
    }

    mc.tool_calls.labels(tool="import_superset_config", status="success" if total_failed == 0 else "partial").inc()
    mc.tool_duration.labels(tool="import_superset_config").observe(time.monotonic() - start_time)

    return json.dumps(report, indent=2, default=str)


async def _import_database(
    manager: ConnectionManager,
    server_id: str,
    db: Dict[str, Any],
    db_mappings: Optional[Dict[str, int]],
    create_missing: bool,
    skip_existing: bool,
) -> Optional[int]:
    """Import a single database, optionally creating it on the target server.

    Checks if a database with the same name already exists on the target.
    If ``db_mappings`` contains the source database ID, uses the mapped target ID.
    Otherwise, creates the database if ``create_missing=True``.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        db: The database resource dict from the export.
        db_mappings: Source-to-target database ID mappings.
        create_missing: Whether to create the database if it doesn't exist.
        skip_existing: Whether to skip if a database with the same name exists.

    Returns:
        Target database ID, or None if skipped.
    """
    source_db_id = str(db.get("id"))
    db_name = db.get("database_name", "")

    # Check db_mappings first
    if db_mappings and source_db_id in db_mappings:
        return db_mappings[source_db_id]

    # Check if database with same name already exists
    dbs_str = await impl_list_resources(manager, server_id, "database")
    dbs_data = _parse_json_result(dbs_str)
    if dbs_data:
        for existing_db in dbs_data.get("result", []):
            if existing_db.get("database_name", "").lower() == db_name.lower():
                if skip_existing:
                    log.info(f"  Database '{db_name}' already exists on target (ID {existing_db['id']})")
                    return existing_db["id"]
                else:
                    return existing_db["id"]

    # Create database if requested
    if create_missing:
        return await _create_database_on_target(manager, server_id, db)

    log.info(f"  Database '{db_name}' not found and create_missing=False, skipping")
    return None


async def _create_database_on_target(
    manager: ConnectionManager,
    server_id: str,
    db: Dict[str, Any],
) -> Optional[int]:
    """Create a database on the target server from exported configuration.

    Creates the database using the Superset API with the database name,
    SQLAlchemy URI, extra configuration, and engine name from the export.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        db: The database resource dict from the export.

    Returns:
        New database ID, or None if creation failed.
    """
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
    # Remove None values
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
) -> Optional[int]:
    """Import a single dataset (physical or virtual) with remapped database reference.

    For physical datasets (with ``table_name``), creates a dataset from the
    specified table on the target database. For virtual datasets (with ``sql``),
    creates a virtual dataset. The database reference is remapped using ``db_id_map``.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        ds: The dataset resource dict from the export.
        db_id_map: Mapping of source database IDs to target database IDs.

    Returns:
        New dataset ID, or None if import failed.
    """
    old_db_id = ds.get("database")
    if isinstance(old_db_id, dict):
        old_db_id = old_db_id.get("id", old_db_id.get("database"))
    elif isinstance(old_db_id, str):
        old_db_id = int(old_db_id)

    new_db_id = db_id_map.get(old_db_id)
    if new_db_id is None:
        log.error(f"  Dataset '{ds.get('table_name')}' references database {old_db_id} which was not imported")
        return None

    # Check if dataset already exists
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

    # Create physical dataset or virtual dataset
    if ds.get("sql"):
        return await _create_virtual_dataset_on_target(manager, server_id, ds, new_db_id)
    else:
        return await _create_physical_dataset_on_target(manager, server_id, ds, new_db_id)


async def _create_physical_dataset_on_target(
    manager: ConnectionManager,
    server_id: str,
    ds: Dict[str, Any],
    database_id: int,
) -> Optional[int]:
    """Create a physical dataset on the target server.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        ds: The dataset resource dict.
        database_id: The target database ID.

    Returns:
        New dataset ID, or None if creation failed.
    """
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
    if ds.get("owners"):
        ds_payload["owners"] = ds["owners"]

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


async def _create_virtual_dataset_on_target(
    manager: ConnectionManager,
    server_id: str,
    ds: Dict[str, Any],
    database_id: int,
) -> Optional[int]:
    """Create a virtual dataset on the target server.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        ds: The dataset resource dict.
        database_id: The target database ID.

    Returns:
        New dataset ID, or None if creation failed.
    """
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
) -> Optional[int]:
    """Import a single chart with remapped datasource reference.

    Creates a chart on the target server using the chart's params and the
    remapped datasource ID. The datasource reference in the params is also
    updated to point to the new dataset.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        chart: The chart resource dict from the export.
        ds_id_map: Mapping of source dataset IDs to target dataset IDs.

    Returns:
        New chart ID, or None if import failed.
    """
    old_ds_id = chart.get("datasource_id")
    if isinstance(old_ds_id, str):
        old_ds_id = int(old_ds_id)

    new_ds_id = ds_id_map.get(old_ds_id)
    if new_ds_id is None:
        log.error(f"  Chart '{chart.get('slice_name')}' references dataset {old_ds_id} which was not imported")
        return None

    datasource_type = chart.get("datasource_type", "table")

    # Parse and update params
    params_raw = chart.get("params", "{}")
    if isinstance(params_raw, str):
        try:
            params = json.loads(params_raw)
        except json.JSONDecodeError:
            params = {}
    else:
        params = params_raw or {}

    # Remap datasource reference in params
    params["datasource_id"] = new_ds_id
    params["datasource"] = f"{new_ds_id}__{datasource_type}"
    params["datasource_type"] = datasource_type

    # Remove source chart id from params if present
    params.pop("id", None)

    # Check if chart already exists
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
        "params": json.dumps(params),
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
) -> Optional[int]:
    """Import a single dashboard with remapped chart references in position_json.

    Creates a dashboard on the target server with a remapped position_json
    where all chart IDs are replaced with their target equivalents.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        dashboard: The dashboard resource dict from the export.
        chart_id_map: Mapping of source chart IDs to target chart IDs.

    Returns:
        New dashboard ID, or None if import failed.
    """
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

    # Check if dashboard already exists
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
        "json_metadata": json.dumps(json_metadata) if json_metadata != {} else None,
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
    """Recursively remap chart IDs in a position_json structure.

    Finds all occurrences of "chartId" or "slice_id" keys in the position JSON
    and replaces their values with the corresponding target chart ID from
    the ``chart_id_map``.

    Args:
        position_json: The dashboard position JSON to modify.
        chart_id_map: Mapping of source chart IDs to target chart IDs.

    Returns:
        New position JSON dict with remapped chart IDs.
    """
    import copy
    result = copy.deepcopy(position_json)

    def _remap(obj: Any) -> Any:
        if isinstance(obj, dict):
            new_dict = {}
            for key, value in obj.items():
                if key in ("chartId", "slice_id") and isinstance(value, (int, str)):
                    old_id = int(value)
                    if old_id in chart_id_map:
                        new_dict[key] = chart_id_map[old_id]
                    else:
                        new_dict[key] = value
                        log.warning(f"  Chart ID {old_id} not found in chart_id_map, keeping original")
                else:
                    new_dict[key] = _remap(value)
            return new_dict
        elif isinstance(obj, list):
            return [_remap(item) for item in obj]
        return obj

    return _remap(result)


async def _import_css_template(
    manager: ConnectionManager,
    server_id: str,
    css: Dict[str, Any],
) -> Optional[int]:
    """Create a CSS template on the target server.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        css: The CSS template resource dict.

    Returns:
        New CSS template ID, or None if creation failed.
    """
    css_payload = {
        "css_template": css.get("css_template", ""),
        "template_name": css.get("template_name", ""),
        "description": css.get("description", ""),
        "expanded": css.get("expanded", False),
        "dataset_ids": css.get("dataset_ids", []),
        "datasource_type": css.get("datasource_type", ""),
    }
    css_payload = {k: v for k, v in css_payload.items() if v is not None and v != ""}

    try:
        resp_str = await impl_superset_api(
            manager, server_id, "POST", "/api/v1/css_template/",
            json_body=json.dumps(css_payload),
        )
        resp_data = _parse_json_result(resp_str)
        if resp_data and "result" in resp_data:
            return resp_data["result"].get("id")
        return None
    except Exception as e:
        log.error(f"Failed to create CSS template: {e}")
        return None


async def _import_annotation(
    manager: ConnectionManager,
    server_id: str,
    annotation: Dict[str, Any],
) -> None:
    """Create an annotation layer on the target server.

    Args:
        manager: ConnectionManager instance.
        server_id: Target server ID.
        annotation: The annotation layer resource dict.
    """
    ann_payload = {
        "name": annotation.get("name", ""),
        "layer_type": annotation.get("layer_type", "TIME_RANGE"),
        "description": annotation.get("description", ""),
        "ends_dttm": annotation.get("ends_dttm"),
        "starts_dttm": annotation.get("starts_dttm"),
        "strong_bottom": annotation.get("strong_bottom", False),
        "strong_top": annotation.get("strong_top", False),
        "opacity": annotation.get("opacity", 0.3),
        "inline": annotation.get("inline", False),
        "name_span": annotation.get("name_span", 0),
        "extra": annotation.get("extra", {}),
    }
    ann_payload = {k: v for k, v in ann_payload.items() if v is not None}

    await impl_superset_api(
        manager, server_id, "POST", "/api/v1/annotation/",
        json_body=json.dumps(ann_payload),
    )
