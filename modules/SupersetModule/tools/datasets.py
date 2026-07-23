"""
Dataset management tools for Apache Superset MCP integration.

Provides tools for listing, creating, and inspecting datasets (both physical
tables and virtual datasets with custom SQL). Also includes database schema
extraction for understanding table structures across different database engines.

MCP Tools Provided:
    - superset_list_datasets: List all datasets on a Superset server
    - superset_get_dataset_info: Get details for a specific dataset
    - superset_create_virtual_dataset: Create a virtual dataset from SQL
    - superset_create_dataset: Create a dataset from a physical table
    - superset_get_database_schema: Extract schema (tables/columns) from a database
"""

import json
import asyncio
import httpx
import time
from typing import List, Optional, Dict, Any, Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import DatasetError
from modules.SupersetModule.schemas.dataset import DatabaseSchemaResponse
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


async def list_datasets(manager: ConnectionManager, server_id: str) -> str:
    """Lists all datasets on a Superset server.
    
    Wrapper around GET /api/v1/dataset/. Fetches the complete list of
    datasets available on the server, including both physical table datasets
    and virtual (SQL-based) datasets.
    
    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
    Returns:
        JSON string containing the list of datasets.
    """
    # Delegate to the generic Superset API executor for the dataset list endpoint
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/dataset/")


async def get_dataset_info(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: Union[int, str]
) -> str:
    """Gets detailed information for a specific dataset.
    
    Fetches the full details of a dataset by its ID, including column
    definitions, metrics, database reference, schema, and SQL expression
    (for virtual datasets).
    
    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        dataset_id: The ID of the dataset to retrieve.
    Returns:
        JSON string containing the dataset details.
    """
    # Delegate to the generic Superset API executor for the dataset detail endpoint
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/dataset/{dataset_id}"
    )


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
     metrics_json: Optional[str] = None
 ) -> str:
     """
     MCP Tool: superset_create_virtual_dataset - Create a virtual dataset from SQL.

     Creates a virtual dataset in Superset by saving a SQL query as a reusable
     data source. Virtual datasets behave like tables in the Superset UI and can
     be used as datasources for charts and dashboards without creating a physical
     database table.

     Args:
         manager: The ConnectionManager instance with Superset connection details.
         server_id: The ID of the configured Superset server.
         dataset_name: The name for the virtual dataset as it will appear in Superset.
         database_id: The numeric ID of the database to execute the SQL against.
         sql: The SQL query that defines the virtual dataset. Must be a SELECT query.
         schema: Optional schema name for databases that support schemas.
         description: Optional human-readable description of the virtual dataset.
         default_endpoint_id: Optional default endpoint ID for the dataset.
         columns_json: Optional JSON string of column definitions to override
             Superset's auto-detected columns. Format: [{"column_name": "...", ...}].
         metrics_json: Optional JSON string of metric definitions. Format:
             [{"metric_name": "...", "expression": "..."}, ...].

     Returns:
         JSON string containing the created virtual dataset's details (ID, name,
         SQL query, database reference) on success, or DatasetError JSON on failure.
     """
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
         mc.record_error(tool="superset_create_virtual_dataset", error_message=f"Server '{server_id}' not found.")
         return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

     start_time = time.monotonic()
     try:
         # Build the virtual dataset payload with required name, database, and SQL fields
         dataset_payload: Dict[str, Any] = {
             "table_name": dataset_name,
             "database": database_id,
             "sql": sql,
         }
         # Attach optional metadata fields only when provided
         if schema:
             dataset_payload["schema"] = schema
         if description:
             dataset_payload["description"] = description
         if default_endpoint_id:
             dataset_payload["default_endpoint_id"] = default_endpoint_id
         if columns_json:
             try:
                 # Parse and validate columns JSON before sending to API
                 dataset_payload["columns"] = json.loads(columns_json)
             except json.JSONDecodeError:
                 mc = get_metrics()
                 mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
                 mc.record_error(tool="superset_create_virtual_dataset", error_message="Invalid JSON in columns_json")
                 return log.collect(DatasetError("'columns_json' is not a valid JSON string.", details=columns_json).to_json())
         if metrics_json:
             try:
                 # Parse and validate metrics JSON before sending to API
                 dataset_payload["metrics"] = json.loads(metrics_json)
             except json.JSONDecodeError:
                 mc = get_metrics()
                 mc.tool_calls.labels(tool="superset_create_virtual_dataset", status="error").inc()
                 mc.record_error(tool="superset_create_virtual_dataset", error_message="Invalid JSON in metrics_json")
                 return log.collect(DatasetError("'metrics_json' is not a valid JSON string.", details=metrics_json).to_json())

         # POST the virtual dataset to Superset's dataset API endpoint
         endpoint = "/api/v1/dataset/"
         resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
         resp.raise_for_status()

         # Record success metrics and return the created dataset details
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


async def create_dataset(
     manager: ConnectionManager,
     server_id: str,
     table_name: str,
     database_id: int,
     schema: Optional[str] = None,
     owners: Optional[List[int]] = None,
     metrics_json: Optional[str] = None,
     columns_json: Optional[str] = None,
     sql_expression: Optional[str] = None
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
             Useful for creating a subset of a large table without a separate view.

     Returns:
         JSON string containing the created dataset's details (ID, name, SQL expression,
         database reference) on success, or DatasetError JSON on failure.
     """
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
         mc.record_error(tool="superset_create_dataset", error_message=f"Server '{server_id}' not found.")
         return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

     start_time = time.monotonic()
     try:
         # Build the dataset payload with required table_name and database fields
         dataset_payload: Dict[str, Any] = {
             "table_name": table_name,
             "database": database_id,
         }
         # Attach optional fields — owners, custom metrics, columns, and SQL expression
         if schema:
             dataset_payload["schema"] = schema
         if owners is not None:
             dataset_payload["owners"] = owners
         if metrics_json:
             try:
                 # Parse and validate metrics JSON before sending to API
                 dataset_payload["metrics"] = json.loads(metrics_json)
             except json.JSONDecodeError:
                 mc = get_metrics()
                 mc.tool_calls.labels(tool="superset_create_dataset", status="error").inc()
                 mc.record_error(tool="superset_create_dataset", error_message="Invalid JSON in metrics_json")
                 return log.collect(DatasetError("'metrics_json' is not valid JSON.", details=metrics_json).to_json())
         if columns_json:
             try:
                 # Parse and validate columns JSON before sending to API
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

         # POST the dataset to Superset's dataset API endpoint
         endpoint = "/api/v1/dataset/"
         resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
         resp.raise_for_status()

         # Record success metrics and return the created dataset details
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

async def get_database_schema(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema_name: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_get_database_schema - Extract schema (tables and columns) from a database.

    Connects to a database via Superset's SQL Lab engine and queries the
    information_schema to discover all tables and their columns. Supports
    PostgreSQL, MySQL/MariaDB, and Microsoft SQL Server engines. Returns
    a structured JSON object with database metadata and column definitions.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to extract schema from.
        schema_name: Optional schema name filter (e.g., 'public', 'dbo').
            Defaults to 'public' for PostgreSQL, database name for MySQL,
            and 'dbo' for MSSQL if not provided.

    Returns:
        JSON string containing database metadata (ID, name, engine) and an
        array of tables, each with a table_name and columns array containing
        column_name, data_type, and is_nullable. Returns DatasetError JSON
        on failure.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

    try:
        # Fetch database details to determine the database engine type
        db_details_str = await impl_get_resource(manager, server_id, "database", database_id)
        try:
            db_details = json.loads(db_details_str)
        except json.JSONDecodeError:
            return log.collect(DatasetError(f"Could not parse database details for ID {database_id}", details=db_details_str).to_json())

        engine = db_details.get("result", {}).get("backend")
        if not engine:
            return log.collect(DatasetError(f"Could not determine database engine for ID {database_id}", details=db_details_str).to_json())

        # Initialize the schema information structure
        schema_info = {
            "database_id": database_id,
            "database_name": db_details.get("result", {}).get("database_name"),
            "engine": engine,
            "tables": []
        }

        table_query = ""
        column_query_template = ""

        # Build engine-specific queries for information_schema table and column discovery
        if engine == "postgresql":
            schema_filter = schema_name or "public"
            table_query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_filter}'
                AND table_type = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = '{schema_filter}'
                AND table_name = '{{table_name}}'
                ORDER BY ordinal_position;
            """
        elif engine in ("mysql", "mariadb"):
            schema_filter = schema_name or db_details.get("result", {}).get("database_name")
            table_query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_filter}'
                AND table_type = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = '{schema_filter}'
                AND table_name = '{{table_name}}'
                ORDER BY ordinal_position;
            """
        elif engine == "mssql":
            schema_filter = schema_name or "dbo"
            table_query = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{schema_filter}'
                AND TABLE_TYPE = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema_filter}'
                AND TABLE_NAME = '{{table_name}}'
                ORDER BY ORDINAL_POSITION;
            """
        else:
            return log.collect(DatasetError(f"Engine '{engine}' not supported for schema extraction").to_json())

        # Execute the table discovery query via SQL Lab to get a list of all tables
        log.info(f"Executing table query for {server_id}/{database_id}")
        table_query_res = await sqllab_execute_query(manager, server_id, database_id, table_query, schema=schema_name)
        table_query_json = json.loads(table_query_res)
        table_client_id = table_query_json.get("result", {}).get("query", {}).get("client_id")
        if not table_client_id:
            return log.collect(DatasetError("Failed to execute table query", details=table_query_res).to_json())

        # Wait briefly then retrieve the table query results
        await asyncio.sleep(2)
        table_results_res = await sqllab_get_query_results(manager, server_id, table_client_id)
        table_results_json = json.loads(table_results_res)
        table_names = [row["table_name"] for row in table_results_json.get("data", [])] if "data" in table_results_json else []

        if not table_names:
            return f"No tables found in database ID {database_id}."

        # For each table, execute a column discovery query to get column definitions
        for table_name in table_names:
            columns = []
            current_column_query = column_query_template.format(table_name=table_name)
            log.info(f"Executing column query for {table_name}")
            column_query_res = await sqllab_execute_query(manager, server_id, database_id, current_column_query, schema=schema_name)
            column_query_json = json.loads(column_query_res)
            column_client_id = column_query_json.get("result", {}).get("query", {}).get("client_id")

            if column_client_id:
                # Wait briefly then retrieve the column query results
                await asyncio.sleep(2)
                column_results_res = await sqllab_get_query_results(manager, server_id, column_client_id)
                column_results_json = json.loads(column_results_res)
                columns = column_results_json.get("data", [])

            # Append the table with its column definitions to the schema structure
            schema_info["tables"].append({
                "table_name": table_name,
                "columns": columns
            })

        # Return the complete schema information as formatted JSON
        return log.collect(json.dumps(schema_info, indent=2))

    except httpx.HTTPStatusError as e:
        log.error(f"HTTPStatusError fetching database schema for {server_id}: {e.response.status_code}")
        return log.collect(DatasetError(
            f"HTTP {e.response.status_code} fetching schema",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json())
    except json.JSONDecodeError as e:
        return log.collect(DatasetError(f"JSON parse error: {e}").to_json())
    except Exception as e:
        log.error(f"Unexpected error fetching database schema for {server_id}: {e}")
        return log.collect(DatasetError(f"Unexpected error fetching schema: {e}", details=str(e)).to_json())
