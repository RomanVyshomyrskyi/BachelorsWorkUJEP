"""
Dataset creation functions for Apache Superset MCP.

Contains functions for creating physical datasets (from tables) and
virtual datasets (from SQL queries) with optional column/metric overrides.
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import httpx

from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import DatasetError
from modules.SupersetModule.manager import ConnectionManager
from modules.log_utils import LogCollector
from modules.metrics import get_metrics
from modules.SupersetModule.tools.dataset.helpers import validate_columns_exist
from modules.SupersetModule.tools.resources import impl_get_resource

log = LogCollector(__name__)


async def create_dataset(
    manager: ConnectionManager,
    server_id: str,
    table_name: str,
    database_id: int,
    schema: Optional[str] = None,
    owners: Optional[List[int]] = None,
    metrics_json: Optional[str] = None,
    columns_json: Optional[str] = None,
    sql_expression: Optional[str] = None,
) -> str:
    """
    MCP Tool: superset_create_dataset - Create a dataset from a physical table.

    Registers an existing database table as a dataset in Superset. This makes
    the table available as a datasource for charts and dashboards. Optionally
    defines custom metrics and column overrides at registration time.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        table_name: The name of the existing database table to register.
        database_id: The numeric ID of the database containing the table.
        schema: Optional schema name (e.g., 'public' for PostgreSQL, 'dbo' for MSSQL).
        owners: Optional list of user IDs who own the dataset.
        metrics_json: Optional JSON string of metric definitions for the table.
        columns_json: Optional JSON string of column definitions to override
            auto-detected columns.
        sql_expression: Optional SQL expression that filters or transforms the table.

    Returns:
        JSON string containing the created dataset's details on success,
        or DatasetError JSON on failure.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
        mc.record_error(tool="superset_create_dataset", error_message=f"Server '{server_id}' not found.")
        return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

    start_time = time.monotonic()
    try:
        dataset_payload: Dict[str, Any] = {
            "table_name": table_name,
            "database": database_id,
        }
        if schema:
            dataset_payload["schema"] = schema
        if owners is not None:
            dataset_payload["owners"] = owners
        if metrics_json:
            try:
                dataset_payload["metrics"] = json.loads(metrics_json)
            except json.JSONDecodeError:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
                mc.record_error(tool="superset_create_dataset", error_message="Invalid JSON in metrics_json")
                return log.collect(DatasetError("'metrics_json' is not valid JSON.", details=metrics_json).to_json())
        if columns_json:
            try:
                dataset_payload["columns"] = json.loads(columns_json)
            except json.JSONDecodeError:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
                mc.record_error(tool="superset_create_dataset", error_message="Invalid JSON in columns_json")
                return log.collect(DatasetError("'columns_json' is not valid JSON.", details=columns_json).to_json())
        if sql_expression:
            dataset_payload["sql_expression"] = sql_expression

        # Verify the database exists before attempting dataset creation
        db_check_result = await impl_get_resource(manager, server_id, "database", database_id)
        if "Error" in db_check_result or "not found" in db_check_result.lower():
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
            mc.record_error(tool="superset_create_dataset", error_message=f"Database ID '{database_id}' not found")
            return log.collect(DatasetError(f"Database ID '{database_id}' not found", details=db_check_result).to_json())

        # Validate columns if specified
        if "columns" in dataset_payload:
            validation_err = await validate_columns_exist(
                manager, server_id, database_id,
                dataset_payload["columns"], "table", table_name,
                table_name=table_name, schema=schema,
            )
            if validation_err:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
                mc.record_error(
                    tool="superset_create_dataset",
                    error_message=f"Column validation failed",
                )
                return log.collect(DatasetError(
                    f"Dataset creation blocked: some columns don't exist in table '{table_name}'",
                    details=f"The following columns specified in columns_json were not found "
                            f"in the actual database table '{table_name}':\n\n"
                            + "\n".join(f"  - {m}" for m in validation_err.strip().split("\n\n")[0].split("\n")[1:])
                            + f"\n\nAvailable columns: see validation details",
                    status_code=400,
                ).to_json())

        endpoint = "/api/v1/dataset/"
        logger.info(f"CREATE_DATASET payload: {json.dumps(dataset_payload, indent=2)}")
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_dataset", status="success").inc()
        mc.tool_duration.labels(tool="superset_create_dataset").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="dataset").inc()
        return log.collect(json.dumps(resp.json(), indent=2))
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
        mc.record_error(tool="superset_create_dataset", error_message=f"HTTP {e.response.status_code} creating dataset", status_code=e.response.status_code)
        log.error(f"HTTPStatusError creating dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return log.collect(DatasetError(
            f"HTTP {e.response.status_code} creating dataset",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json())
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
        mc.record_error(tool="superset_create_dataset", error_message=str(e))
        log.error(f"Unexpected error creating dataset for {server_id}: {e}")
        return log.collect(DatasetError(f"Unexpected error creating dataset: {e}", details=str(e)).to_json())
