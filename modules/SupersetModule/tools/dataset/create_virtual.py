"""
Virtual dataset creation for Apache Superset MCP.

Contains function for creating virtual datasets from SQL queries
with optional column and metric overrides.
"""

import json
import time
from typing import Any, Dict, Optional

import httpx

from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import DatasetError
from modules.SupersetModule.manager import ConnectionManager
from modules.log_utils import LogCollector
from modules.metrics import get_metrics
from modules.SupersetModule.tools.dataset.helpers import validate_columns_exist

log = LogCollector(__name__)


async def create_virtual_dataset(
    manager: ConnectionManager,
    server_id: str,
    dataset_name: str,
    database_id: int,
    sql: str,
    schema: Optional[str] = None,
    description: Optional[str] = None,
    default_endpoint_id: Optional[int] = None,
    columns_json: Optional[str] = None,
    metrics_json: Optional[str] = None,
) -> str:
    """
    MCP Tool: superset_create_virtual_dataset - Create a virtual dataset from SQL.

    Creates a virtual dataset in Superset by saving a SQL query as a reusable
    data source. Virtual datasets behave like tables in the Superset UI and can
    be used as datasources for charts and dashboards.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dataset_name: The name for the virtual dataset as it will appear in Superset.
        database_id: The numeric ID of the database to execute the SQL against.
        sql: The SQL query that defines the virtual dataset. Must be a SELECT query.
        schema: Optional schema name for databases that support schemas.
        description: Optional human-readable description of the virtual dataset.
        default_endpoint_id: Optional default endpoint ID for the dataset.
        columns_json: Optional JSON string of column definitions.
        metrics_json: Optional JSON string of metric definitions.

    Returns:
        JSON string containing the created virtual dataset's details on success,
        or DatasetError JSON on failure.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
        mc.record_error(tool="superset_create_virtual_dataset", error_message=f"Server '{server_id}' not found.")
        return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

    start_time = time.monotonic()
    try:
        dataset_payload: Dict[str, Any] = {
            "table_name": dataset_name,
            "database": database_id,
            "sql": sql,
        }
        if schema:
            dataset_payload["schema"] = schema
        if description:
            dataset_payload["description"] = description
        if default_endpoint_id:
            dataset_payload["default_endpoint_id"] = default_endpoint_id
        if columns_json:
            try:
                dataset_payload["columns"] = json.loads(columns_json)
            except json.JSONDecodeError:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
                mc.record_error(tool="superset_create_virtual_dataset", error_message="Invalid JSON in columns_json")
                return log.collect(DatasetError("'columns_json' is not a valid JSON string.", details=columns_json).to_json())
        if metrics_json:
            try:
                dataset_payload["metrics"] = json.loads(metrics_json)
            except json.JSONDecodeError:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
                mc.record_error(tool="superset_create_virtual_dataset", error_message="Invalid JSON in metrics_json")
                return log.collect(DatasetError("'metrics_json' is not a valid JSON string.", details=metrics_json).to_json())

        # Validate columns_json entries exist in the SQL query result
        if "columns" in dataset_payload:
            validation_err = await validate_columns_exist(
                manager, server_id, database_id,
                dataset_payload["columns"], "virtual_dataset", dataset_name,
                sql=sql, schema=schema,
            )
            if validation_err:
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
                mc.record_error(
                    tool="superset_create_virtual_dataset",
                    error_message=f"Column validation failed",
                )
                return log.collect(DatasetError(
                    "Virtual dataset creation blocked: some columns don't exist in the SQL result",
                    details=f"The following columns specified in columns_json were not found "
                            f"in the SQL query result for '{dataset_name}':\n\n"
                            + "\n".join(f"  - {m}" for m in validation_err.strip().split("\n\n")[0].split("\n")[1:]),
                    status_code=400,
                ).to_json())

        endpoint = "/api/v1/dataset/"
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="success").inc()
        mc.tool_duration.labels(tool="superset_create_virtual_dataset").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="dataset").inc()
        return log.collect(json.dumps(resp.json(), indent=2))
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
        mc.record_error(tool="superset_create_virtual_dataset", error_message=f"HTTP {e.response.status_code} creating virtual dataset", status_code=e.response.status_code)
        log.error(f"HTTPStatusError creating virtual dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return log.collect(DatasetError(
            f"HTTP {e.response.status_code} creating virtual dataset",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json())
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
        mc.record_error(tool="superset_create_virtual_dataset", error_message=str(e))
        log.error(f"Unexpected error creating virtual dataset for {server_id}: {e}")
        return log.collect(DatasetError(f"Unexpected error creating virtual dataset: {e}", details=str(e)).to_json())
