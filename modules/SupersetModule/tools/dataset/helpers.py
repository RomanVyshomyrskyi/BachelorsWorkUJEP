"""
Shared validation helpers for dataset creation.

Contains common column validation logic used by both create_dataset
and create_virtual_dataset to verify columns exist in the data source.
"""

import asyncio
import json
import logging
from difflib import get_close_matches
from typing import Any, Dict, List, Optional

from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results

logger = logging.getLogger(__name__)


async def validate_columns_exist(
    manager,
    server_id: str,
    database_id: int,
    specified_columns: List[Any],
    source_type: str,  # 'virtual_dataset' or 'table'
    source_name: str,
    sql: Optional[str] = None,
    table_name: Optional[str] = None,
    schema: Optional[str] = None,
) -> Optional[str]:
    """
    Validate that specified columns exist in the SQL result or database table.

    Executes an introspection query and checks that all columns in the
    specified_columns list exist in the actual data source.

    Args:
        manager: ConnectionManager instance
        server_id: Superset server ID
        database_id: Database connection ID
        specified_columns: List of column definitions (strings or dicts)
        source_type: 'virtual_dataset' or 'table'
        source_name: Name of the dataset or table
        sql: SQL query (for virtual datasets)
        table_name: Table name (for physical tables)
        schema: Optional schema name

    Returns:
        Error message string if validation fails, None if all columns are valid
    """
    if source_type == "virtual_dataset" and sql:
        introspect_sql = f"SELECT * FROM ({sql}) AS _introspect LIMIT 0"
    elif source_type == "table" and table_name:
        schema_ref = schema or "public"
        introspect_sql = f"SELECT * FROM {schema_ref}.{table_name} LIMIT 0"
    else:
        logger.warning(f"Cannot introspect {source_type} '{source_name}': missing parameters")
        return None

    try:
        exec_raw = await sqllab_execute_query(
            manager, server_id, database_id, introspect_sql, schema=schema
        )
        exec_data = json.loads(exec_raw)
        client_id = exec_data.get("result", {}).get("query", {}).get("client_id")
        if not client_id:
            logger.warning(f"No client_id from introspection of {source_type} '{source_name}'")
            return None

        await asyncio.sleep(1)
        results_raw = await sqllab_get_query_results(manager, server_id, client_id)
        results = json.loads(results_raw)
        actual_columns = [c.get("column_name", "") for c in results.get("columns", [])]
        if not actual_columns:
            logger.info(f"No columns returned from introspection of {source_type} '{source_name}'")
            return None

        actual_set = {c.lower() for c in actual_columns}
        missing = []
        for scol in specified_columns:
            if isinstance(scol, dict):
                col_name = scol.get("column_name", "")
            else:
                col_name = str(scol)
            if col_name.lower() not in actual_set:
                suggestions = get_close_matches(col_name.lower(), list(actual_set), n=3, cutoff=0.6)
                sug = f" Did you mean: {', '.join(suggestions)}?" if suggestions else ""
                missing.append(f"'{col_name}'{sug}")

        if missing:
            return (
                f"The following columns specified in columns_json were not found "
                f"in the {source_type.replace('_', ' ')} '{source_name}':\n\n"
                + "\n".join(f"  - {m}" for m in missing)
                + f"\n\n{source_type.replace('_', ' ').title()} columns: {', '.join(actual_columns)}"
            )
    except Exception as e:
        logger.warning(f"Column introspection failed for {source_type} '{source_name}': {e}")
        # Proceed despite introspection failure - best-effort validation

    return None
