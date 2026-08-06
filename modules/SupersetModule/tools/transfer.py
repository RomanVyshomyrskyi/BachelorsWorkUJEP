"""
Dashboard and chart transfer tools between Superset servers.

This module implements a 3-phase transfer pipeline (datasets → charts → dashboard)
for migrating dashboards and their dependencies between Superset instances.
It supports both ``export_import`` (native Superset import/export) and
``json_copy`` (manual GET/POST) transfer strategies, automatic database
and table mapping resolution, chart recreation with datasource remapping,
and incremental diff reporting against destination charts.

Key Functions:
    - ``transfer_dashboard()``: Full 3-phase dashboard transfer with reporting.
    - ``impl_transfer_item()``: Low-level single resource transfer via strategy.
    - ``_resolve_dataset()``: Resolve and recreate datasets on the target server.
    - ``_recreate_chart()``: Clone a chart with remapped datasource references.
    - ``_remap_chart_ids_in_position_json()``: Update position_json with new IDs.
"""

import json
import asyncio
import time
from typing import Union, Optional, Dict, Any, Tuple, List
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import TRANSFER_STRATEGY, RESOURCE_ENDPOINTS
from modules.SupersetModule.api_client import ensure_auth, execute_request
from modules.SupersetModule.tools.resources import impl_get_resource, impl_list_resources
from modules.SupersetModule.tools.datasets import create_dataset
from modules.SupersetModule.tools.charts import create_chart
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.exceptions import TransferError
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)
NEED_INPUT_PREFIX = "NEED_INPUT:"

async def impl_transfer_item(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    resource_type: str,
    item_id: Union[int, str]
) -> str:
    """Transfer a single resource item between Superset servers.

    Selects the transfer strategy from ``TRANSFER_STRATEGY`` based on
    resource type: ``export_import`` for charts/dashboards/databases/datasets,
    ``json_copy`` for other types. Handles authentication, export, and import
    phases for both strategies.

    Description:
        For ``export_import``: GETs the export ZIP from the source server
        (with query param ``q=[item_id]``), then POSTs it as multipart/form-data
        to the target server's import endpoint with ``overwrite=true``.
        For ``json_copy``: GETs the item detail from the source, strips
        read-only metadata fields (id, created_by, etc.), and POSTs the
        sanitized payload to create a clone on the target.

    Args:
        manager: ConnectionManager with source and target server configs.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        resource_type: Superset resource type (e.g. "chart", "dashboard").
        item_id: Integer or string ID of the resource to transfer.

    Returns:
        JSON string with a success message or a TransferError JSON on failure.

    Example:
        result = await impl_transfer_item(
            manager, source_server_id="source", target_server_id="target",
            resource_type="chart", item_id=123
        )
        # Returns JSON with success message or TransferError details.
    """
    source_ctx = manager.get_context(source_server_id)
    target_ctx = manager.get_context(target_server_id)

    if not source_ctx or not target_ctx:
        return log_impl.collect(TransferError("Source or target server not found.", status_code=404).to_json())

    strategy = TRANSFER_STRATEGY.get(resource_type, "json_copy")

    log_impl = LogCollector(__name__)

    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)

        if strategy == "export_import":
            q_param = json.dumps([item_id])
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            export_url = f"{endpoint_base}/export/"

            log_impl.info(f"Exporting {resource_type} {item_id} from {source_server_id}...")
            export_resp = await execute_request(source_ctx, "GET", export_url, params={"q": q_param})

            if export_resp.status_code != 200:
                return log_impl.collect(TransferError(
                    f"Export failed: HTTP {export_resp.status_code}",
                    status_code=export_resp.status_code,
                    details=export_resp.text,
                ).to_json())

            import_url = f"{endpoint_base}/import/"
            file_name = f"export_{resource_type}_{item_id}.zip"

            files = {'formData': (file_name, export_resp.content, 'application/zip')}
            data = {'overwrite': 'true', 'passwords': '{}'}

            log_impl.info(f"Importing to {target_server_id}...")
            import_resp = await execute_request(target_ctx, "POST", import_url, files=files, data=data)

            if import_resp.status_code not in [200, 201]:
                return log_impl.collect(TransferError(
                    f"Import failed: HTTP {import_resp.status_code}",
                    status_code=import_resp.status_code,
                    details=import_resp.text,
                ).to_json())

            return log_impl.collect(json.dumps({"message": f"Successfully transferred {resource_type} {item_id}."}))

        elif strategy == "json_copy":
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")

            detail_url = f"{endpoint_base}/{item_id}"
            get_resp = await execute_request(source_ctx, "GET", detail_url)
            if get_resp.status_code != 200:
                return log_impl.collect(TransferError(
                    f"Failed to get item from source: HTTP {get_resp.status_code}",
                    status_code=get_resp.status_code,
                ).to_json())

            item_data = get_resp.json().get("result")
            if not item_data:
                return log_impl.collect(TransferError("Source item data not found in response.").to_json())

            params_to_remove = ['id', 'created_by', 'changed_by', 'created_on', 'changed_on', 'owners']
            payload = {k: v for k, v in item_data.items() if k not in params_to_remove}

            post_url = f"{endpoint_base}/"
            create_resp = await execute_request(target_ctx, "POST", post_url, json=payload)

            if create_resp.status_code not in [200, 201]:
                return log_impl.collect(TransferError(
                    f"Failed to create on target: HTTP {create_resp.status_code}",
                    status_code=create_resp.status_code,
                    details=create_resp.text,
                ).to_json())

            return log_impl.collect(json.dumps({"message": f"Successfully transferred {resource_type} {item_id} (created new ID)."}))

        else:
            return log_impl.collect(TransferError(f"Unknown transfer strategy for {resource_type}").to_json())

    except Exception as e:
        return log_impl.collect(TransferError(f"Transfer error: {e}", details=str(e)).to_json())


def _need_input(resource_type: str, source_id: Any, name: str, available: list) -> str:
    """Build a ``NEED_INPUT`` prefix message requesting user intervention.

    Used when automatic resolution fails (e.g., no matching database or table
    found on the target server). The caller can parse the JSON payload after
    the ``NEED_INPUT:`` prefix to present options to the user.

    Args:
        resource_type: Type of resource needing input (e.g. "database").
        source_id: ID of the resource on the source server.
        name: Human-readable name of the resource.
        available: List of available options on the target server.

    Returns:
        String with ``NEED_INPUT:`` prefix followed by a JSON payload
        containing type, source_id, name, and available options.
    """
    payload = {
        "type": resource_type,
        "source_id": source_id,
        "name": name,
        "available": available
    }
    return f"{NEED_INPUT_PREFIX}{json.dumps(payload)}"


def _parse_json_result(result_str: str) -> Optional[Dict]:
    """Parse a JSON string result safely, returning None on failure.

    Args:
        result_str: Raw JSON string to parse.

    Returns:
        Parsed dict on success, None if the string is not valid JSON.
    """
    try:
        return json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return None


async def _resolve_target_database(
    manager: ConnectionManager,
    source_db_id: int,
    source_db_name: str,
    target_server_id: str,
    db_mappings: Dict[int, int]
) -> Tuple[Optional[int], Optional[str]]:
    """Find or map a source database to its equivalent on the target server.

    Checks the ``db_mappings`` dictionary first for a pre-configured mapping,
    then falls back to listing all databases on the target and matching by
    case-insensitive name. Returns a ``NEED_INPUT`` message with available
    options if no match is found.

    Args:
        manager: ConnectionManager instance.
        source_db_id: Database ID on the source Superset server.
        source_db_name: Database name to match on the target.
        target_server_id: Target Superset server ID.
        db_mappings: Pre-configured source-to-target database ID mappings.

    Returns:
        Tuple of (target_database_id, error_message). On success,
        target_database_id is an integer and error_message is None.
        On failure, target_database_id is None and error_message contains
        either a description or a ``NEED_INPUT:`` JSON payload.
    """
    if source_db_id in db_mappings:
        return db_mappings[source_db_id], None

    dbs_str = await impl_list_resources(manager, target_server_id, "database")
    dbs_data = _parse_json_result(dbs_str)
    if not dbs_data:
        return None, f"Could not list databases on target: {dbs_str}"

    dbs = dbs_data.get("result", [])
    if not isinstance(dbs, list):
        return None, f"Unexpected database list format: {dbs_data}"

    for db in dbs:
        if db.get("database_name", "").lower() == source_db_name.lower():
            return db["id"], None

    available_dbs = [{"id": db["id"], "name": db.get("database_name", "")} for db in dbs if "id" in db]
    return None, _need_input("database", source_db_id, source_db_name, available_dbs)


async def _find_existing_dataset(
    manager: ConnectionManager,
    target_server_id: str,
    target_db_id: int,
    table_name: str,
    schema: Optional[str] = None
) -> Optional[int]:
    """Find an existing dataset on the target server by table name.

    Lists all datasets on the target server and finds one that matches
    the given table name and schema. Returns the dataset ID if found,
    None otherwise.

    Args:
        manager: ConnectionManager instance.
        target_server_id: Target Superset server ID.
        target_db_id: Database ID on the target server.
        table_name: Table name to search for.
        schema: Optional schema name to filter by.

    Returns:
        Dataset ID if found, None otherwise.
    """
    ds_list_str = await impl_list_resources(manager, target_server_id, "dataset")
    ds_list_data = _parse_json_result(ds_list_str)
    if not ds_list_data:
        return None
    datasets = ds_list_data.get("result", [])
    if not isinstance(datasets, list):
        return None
    for ds in datasets:
        ds_info_str = await impl_get_resource(manager, target_server_id, "dataset", ds.get("id", 0))
        ds_info = _parse_json_result(ds_info_str)
        if not ds_info:
            continue
        result = ds_info.get("result", {})
        ds_table = result.get("table_name", "")
        ds_schema = result.get("schema")
        ds_db = result.get("database", {})
        if isinstance(ds_db, dict):
            ds_db_id = ds_db.get("id")
        else:
            ds_db_id = ds_db
        if ds_table == table_name and ds_db_id == target_db_id:
            if schema is None or ds_schema == schema or (not ds_schema and not schema):
                log.info(f"Found existing dataset for '{table_name}': ID {ds.get('id')}")
                return ds.get("id")
    return None


async def _check_table_exists(
    manager: ConnectionManager,
    target_server_id: str,
    target_db_id: int,
    schema: Optional[str],
    table_name: str
) -> bool:
    """Check if a table exists on the target database via SQL Lab query.

    Uses engine-specific information_schema queries (PostgreSQL, MySQL, MSSQL)
    to determine table existence. Falls back to a ``LIMIT 1`` probe query for
    unknown database engines.

    Args:
        manager: ConnectionManager instance.
        target_server_id: Target Superset server ID.
        target_db_id: Database ID on the target server.
        schema: Optional database schema name.
        table_name: Table name to check for existence.

    Returns:
        True if the table exists on the target database, False otherwise.
    """
    db_detail_str = await impl_get_resource(manager, target_server_id, "database", target_db_id)
    db_detail = _parse_json_result(db_detail_str)
    if not db_detail:
        return False

    engine = db_detail.get("result", {}).get("backend", "")

    if engine == "postgresql":
        schema_filter = schema or "public"
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_filter}' AND table_name = '{table_name}' AND table_type = 'BASE TABLE'"
    elif engine == "mysql":
        schema_filter = schema or db_detail.get("result", {}).get("database_name")
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_filter}' AND table_name = '{table_name}' AND table_type = 'BASE TABLE'"
    elif engine == "mssql":
        schema_filter = schema or "dbo"
        query = f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{schema_filter}' AND TABLE_NAME = '{table_name}' AND TABLE_TYPE = 'BASE TABLE'"
    else:
        query = f"SELECT * FROM {schema + '.' if schema else ''}{table_name} LIMIT 1"

    res = await sqllab_execute_query(manager, target_server_id, target_db_id, query, schema=schema)
    res_data = _parse_json_result(res)
    if not res_data:
        log.info(f"Table check: failed to parse execute response for table '{table_name}'")
        return False

    # Try to get data directly from the execute response (modern Superset API)
    data = res_data.get("data", [])
    row_count = len(data) if data else 0

    if row_count == 0:
        # Fallback: try to get results via sqllab_get_query_results
        client_id = res_data.get("result", {}).get("query", {}).get("client_id") or res_data.get("query", {}).get("id")
        if client_id:
            await asyncio.sleep(2)
            results = await sqllab_get_query_results(manager, target_server_id, client_id)
            results_data = _parse_json_result(results)
            if results_data:
                data = results_data.get("data", [])
                row_count = len(data) if data else 0

    log.info(f"Table check: table '{table_name}' -> found {row_count} rows, exists={row_count > 0}")
    return row_count > 0


async def _resolve_dataset(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    source_ds_id: int,
    db_mappings: Dict[int, int],
    table_mappings: Dict[str, str],
    expected_columns: Optional[List[str]] = None,
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    """Resolve a source dataset to a new dataset on the target server.

    Fetches the source dataset's details (table name, schema, database, SQL),
    resolves the target database and table, checks table existence, then
    creates a new dataset on the target via ``create_dataset()``.

    Description:
        This is the dataset phase of the 3-phase transfer pipeline. It handles
        both physical tables and virtual datasets (SQL expressions). Virtual
        datasets are re-created with their original SQL, while physical tables
        must exist on the target database. When ``expected_columns`` is provided,
        validates that the target dataset has all the expected columns before
        returning success.

    Args:
        manager: ConnectionManager instance.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        source_ds_id: Source dataset ID to resolve.
        db_mappings: Pre-configured database ID mappings.
        table_mappings: Pre-configured table name mappings.
        expected_columns: Optional list of column names expected by charts
            referencing this dataset. Validated against the target dataset
            after creation.

    Returns:
        Tuple of (new_dataset_id, datasource_type, error_message).
        On success: (int_id, "table"|"query", None).
        On failure: (None, None, error_string) or
        (None, None, NEED_INPUT_string) if user input required.
    """
    ds_str = await impl_get_resource(manager, source_server_id, "dataset", source_ds_id)
    ds_data = _parse_json_result(ds_str)
    if not ds_data:
        return None, None, f"Could not get dataset {source_ds_id} from source: {ds_str}"

    ds_result = ds_data.get("result", {})
    table_name = ds_result.get("table_name", "")
    schema = ds_result.get("schema")
    sql_expression = ds_result.get("sql")
    source_db_id = ds_result.get("database", {}).get("id")

    if not source_db_id:
        db_info = ds_result.get("database", {})
        return None, None, f"Dataset {source_ds_id} has no database info: {db_info}"

    db_str = await impl_get_resource(manager, source_server_id, "database", source_db_id)
    db_data = _parse_json_result(db_str)
    if not db_data:
        return None, None, f"Could not get database {source_db_id} from source: {db_str}"

    db_result = db_data.get("result", {})
    source_db_name = db_result.get("database_name", "")

    target_db_id, err = await _resolve_target_database(
        manager, source_db_id, source_db_name, target_server_id, db_mappings
    )
    if err:
        return None, None, err

    mapped_table = table_mappings.get(table_name, table_name)

    table_exists = await _check_table_exists(manager, target_server_id, target_db_id, schema, mapped_table)
    if not table_exists:
        return None, None, _need_input("table", table_name, mapped_table, [])

    # Check if a dataset with this table already exists on the target
    existing_ds_id = await _find_existing_dataset(manager, target_server_id, target_db_id, mapped_table, schema)
    if existing_ds_id:
        log.info(f"Using existing dataset ID {existing_ds_id} for '{mapped_table}'")
        return existing_ds_id, "table", None

    dataset_result_str = await create_dataset(
        manager,
        target_server_id,
        table_name=mapped_table,
        database_id=target_db_id,
        schema=schema,
        sql_expression=sql_expression
    )
    if "Error" in dataset_result_str:
        return None, None, f"Failed to create dataset '{mapped_table}' on target: {dataset_result_str}"

    dataset_result = _parse_json_result(dataset_result_str)
    if not dataset_result:
        return None, None, f"Could not parse dataset creation result: {dataset_result_str}"

    new_ds_id = dataset_result.get("id")
    if not new_ds_id:
        return None, None, f"Dataset created but no ID returned: {dataset_result_str}"

    if expected_columns:
        try:
            ds_info_raw = await impl_get_resource(manager, target_server_id, "dataset", new_ds_id)
            ds_info = _parse_json_result(ds_info_raw)
            if ds_info:
                target_columns = [
                    c.get("column_name", "").lower()
                    for c in ds_info.get("result", {}).get("columns", [])
                ]
                if target_columns:
                    target_set = set(target_columns)
                    missing = [
                        col for col in expected_columns
                        if col.lower() not in target_set
                    ]
                    if missing:
                        return None, None, (
                            f"Target dataset '{mapped_table}' is missing columns required "
                            f"by source charts: {', '.join(missing)}.\n"
                            f"Available columns: {', '.join(target_columns[:20])}"
                        )
        except Exception:
            pass  # Best-effort validation, proceed on failure

    return new_ds_id, ds_result.get("datasource_type", "table"), None


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

    Description:
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
    ds_str = await impl_get_resource(manager, source_server_id, "dataset", datasource_id)
    ds_data = _parse_json_result(ds_str)
    if not ds_data:
        return None
    sql = ds_data.get("result", {}).get("sql")
    return sql if sql and sql.strip() else None


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
        Dict mapping source chart ID → destination chart detail dict.
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
        db_mappings: Optional JSON string of source→target database ID mappings
            (e.g. ``'{"1": 2, "3": 4}'``).
        table_mappings: Optional JSON string of source→target table name mappings
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

    transfer_start = time.time()
    report: Dict[str, Any] = {
        "source": {"server_id": source_server_id, "base_url": getattr(source_ctx.config, "base_url", "")},
        "destination": {"server_id": target_server_id, "base_url": getattr(target_ctx.config, "base_url", "")},
        "dashboard": {},
        "datasets": [],
        "charts": [],
        "execution": {
            "datasets": [],
            "charts": [],
            "dashboard": {},
        },
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

    # Extract chart IDs from position_json (reliable across Superset versions)
    source_chart_ids = []
    position_json = dash_result.get("position_json")
    if position_json:
        try:
            if isinstance(position_json, str):
                pos_data = json.loads(position_json)
            else:
                pos_data = position_json
            # Recursively find all chartId references
            def find_chart_ids(obj, found=None):
                if found is None:
                    found = set()
                if isinstance(obj, dict):
                    cid = obj.get("chartId") or obj.get("slice_id")
                    if cid is not None:
                        try:
                            found.add(int(cid))
                        except (ValueError, TypeError):
                            pass
                    for v in obj.values():
                        find_chart_ids(v, found)
                elif isinstance(obj, list):
                    for item in obj:
                        find_chart_ids(item, found)
                return found
            source_chart_ids = sorted(find_chart_ids(pos_data))
            log.info(f"Extracted {len(source_chart_ids)} chart IDs from position_json: {source_chart_ids}")
        except Exception as e:
            log.info(f"Failed to parse position_json for chart IDs: {e}")

    # Fallback: try to extract IDs from source_charts list
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

    if not unique_ds_ids:
        report["errors"].append("No datasources found in source charts")
        return json.dumps(report, indent=2, default=str)

    log.info(f"Dashboard requires {len(unique_ds_ids)} unique datasets")

    dest_matches = await _find_matching_charts_at_destination(manager, target_server_id, chart_details)
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

    log.info(f"Phase 1: Resolving {len(unique_ds_ids)} unique datasources (reverse hierarchy)...")

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
                            import re
                            m = re.match(r"^(?:SUM|AVG|MIN|MAX|COUNT|COUNT_DISTINCT)\s*\(\s*(.+?)\s*\)$", v, re.IGNORECASE)
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
                return err
            entry["error"] = err
            ds_errors += 1
            report["errors"].append(f"Dataset {old_ds_id}: {err}")
        else:
            ds_mapping[old_ds_id] = (new_ds_id, resolved_ds_type or ds_type)
            log.info(f"  Dataset {old_ds_id} -> {new_ds_id}")
        report["execution"]["datasets"].append(entry)

    if ds_errors > 0:
        report["success_rate"] = f"0% — dataset resolution failed"
        return json.dumps(report, indent=2, default=str)

    log.info(f"Phase 2: Recreating {len(source_chart_ids)} charts...")
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

    if chart_errors > 0:
        report["success_rate"] = f"0% — chart recreation failed"
        return json.dumps(report, indent=2, default=str)

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
