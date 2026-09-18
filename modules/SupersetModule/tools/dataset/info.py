"""
Dataset info tools for Apache Superset MCP.

Contains functions for listing datasets, getting dataset details,
and extracting database schemas from various database engines.
"""

import asyncio
import json
import logging
from typing import Optional

import httpx

from modules.SupersetModule.exceptions import DatasetError
from modules.SupersetModule.manager import ConnectionManager
from modules.log_utils import LogCollector
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results

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
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/dataset/")


async def get_dataset_info(
    manager: ConnectionManager,
    server_id: str,
    dataset_id
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
    return await impl_superset_api(
        manager, server_id, "GET", f"/api/v1/dataset/{dataset_id}"
    )


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
    PostgreSQL, MySQL/MariaDB, and Microsoft SQL Server engines.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to extract schema from.
        schema_name: Optional schema name filter (e.g., 'public', 'dbo').

    Returns:
        JSON string containing database metadata and an array of tables
        with column definitions. Returns DatasetError JSON on failure.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json())

    try:
        db_details_str = await impl_get_resource(manager, server_id, "database", database_id)
        try:
            db_details = json.loads(db_details_str)
        except json.JSONDecodeError:
            return log.collect(DatasetError(f"Could not parse database details for ID {database_id}", details=db_details_str).to_json())

        engine = db_details.get("result", {}).get("backend")
        if not engine:
            return log.collect(DatasetError(f"Could not determine database engine for ID {database_id}", details=db_details_str).to_json())

        schema_info = {
            "database_id": database_id,
            "database_name": db_details.get("result", {}).get("database_name"),
            "engine": engine,
            "tables": []
        }

        table_query, column_query_template = _build_schema_queries(engine, schema_name, db_details)

        if not table_query:
            return log.collect(DatasetError(f"Engine '{engine}' not supported for schema extraction").to_json())

        # Execute table discovery query
        log.info(f"Executing table query for {server_id}/{database_id}")
        table_query_res = await sqllab_execute_query(manager, server_id, database_id, table_query, schema=schema_name)
        table_query_json = json.loads(table_query_res)
        # Superset API returns data directly in execute response
        table_data = table_query_json.get("data")
        if not table_data:
            # Fallback: try to get client_id and fetch results
            table_client_id = table_query_json.get("client_id") or table_query_json.get("query", {}).get("id")
            if table_client_id:
                await asyncio.sleep(2)
                table_results_res = await sqllab_get_query_results(manager, server_id, table_client_id)
                table_results_json = json.loads(table_results_res)
                table_data = table_results_json.get("data") or table_results_json.get("result", {}).get("data", [])
        table_names = [row["table_name"] for row in table_data] if table_data else []

        if not table_names:
            return f"No tables found in database ID {database_id}."

        # Get column definitions for each table
        for table_name in table_names:
            columns = await _fetch_table_columns(
                manager, server_id, database_id, column_query_template, table_name, schema_name
            )
            schema_info["tables"].append({"table_name": table_name, "columns": columns})

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


def _build_schema_queries(engine, schema_name, db_details):
    """Build engine-specific SQL queries for schema extraction."""
    if engine == "postgresql":
        schema_filter = schema_name or "public"
        table_query = f"""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = '{schema_filter}' AND table_type = 'BASE TABLE';
        """
        column_query_template = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = '{schema_filter}' AND table_name = '{{table_name}}'
            ORDER BY ordinal_position;
        """
    elif engine in ("mysql", "mariadb"):
        schema_filter = schema_name or db_details.get("result", {}).get("database_name")
        table_query = f"""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = '{schema_filter}' AND table_type = 'BASE TABLE';
        """
        column_query_template = f"""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = '{schema_filter}' AND table_name = '{{table_name}}'
            ORDER BY ordinal_position;
        """
    elif engine == "mssql":
        schema_filter = schema_name or "dbo"
        table_query = f"""
            SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES
            WHERE TABLE_SCHEMA = '{schema_filter}' AND TABLE_TYPE = 'BASE TABLE';
        """
        column_query_template = f"""
            SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{schema_filter}' AND TABLE_NAME = '{{table_name}}'
            ORDER BY ORDINAL_POSITION;
        """
    else:
        return None, None

    return table_query, column_query_template


async def _fetch_table_columns(manager, server_id, database_id, column_query_template, table_name, schema_name):
    """Fetch column definitions for a single table."""
    columns = []
    current_column_query = column_query_template.format(table_name=table_name)
    log.info(f"Executing column query for {table_name}")
    column_query_res = await sqllab_execute_query(manager, server_id, database_id, current_column_query, schema=schema_name)
    column_query_json = json.loads(column_query_res)
    # Superset API returns data directly in execute response
    columns = column_query_json.get("data") or []
    if not columns:
        # Fallback: try to get client_id and fetch results
        column_client_id = column_query_json.get("client_id") or column_query_json.get("query", {}).get("id")
        if column_client_id:
            await asyncio.sleep(2)
            column_results_res = await sqllab_get_query_results(manager, server_id, column_client_id)
            column_results_json = json.loads(column_results_res)
            columns = column_results_json.get("data") or column_results_json.get("result", {}).get("data", [])

    return columns
