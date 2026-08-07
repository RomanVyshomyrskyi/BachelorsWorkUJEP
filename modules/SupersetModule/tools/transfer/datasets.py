"""
Dashboard and chart transfer tools between Superset servers.

Database resolution functions for the transfer pipeline.
"""

from typing import Optional, Dict, Tuple
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.resources import impl_list_resources
from modules.SupersetModule.tools.transfer.core import _parse_json_result, _need_input


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
        ds_info_str = await impl_list_resources(manager, target_server_id, "dataset")
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
                return ds.get("id")
    return None
