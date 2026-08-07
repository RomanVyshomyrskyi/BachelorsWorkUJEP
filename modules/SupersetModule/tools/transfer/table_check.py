"""
Dashboard and chart transfer tools between Superset servers.

Table existence checking and dataset resolution functions.
"""

from typing import Optional, Dict, Tuple, List
import asyncio
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.datasets import create_dataset
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.tools.transfer.core import _parse_json_result, _need_input
from modules.SupersetModule.tools.transfer.datasets import _resolve_target_database, _find_existing_dataset
from modules.log_utils import LogCollector

log = LogCollector(__name__)


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
