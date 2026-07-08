import json
import asyncio
import logging
import httpx
from typing import List, Optional, Dict, Any, Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.resources import impl_get_resource
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results
from modules.SupersetModule.tools.general import impl_superset_api

logger = logging.getLogger(__name__)


async def list_datasets(manager: ConnectionManager, server_id: str) -> str:
    """Lists all datasets on a Superset server.
    
    Wrapper around GET /api/v1/dataset/.
    
    Args:
        server_id: The ID of the configured Superset server.
    Returns:
        JSON string containing the list of datasets.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/dataset/")


async def get_dataset_info(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: Union[int, str]
) -> str:
    """Gets detailed information for a specific dataset.
    
    Args:
        server_id: The ID of the configured Superset server.
        dataset_id: The ID of the dataset to retrieve.
    Returns:
        JSON string containing the dataset details.
    """
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
    """Save a SQL query as a virtual dataset for charting.
    
    Creates a virtual dataset from a SQL query that can be used
    to create charts. This is the official tool name matching
    the Apache Superset MCP service.
    
    Args:
        server_id: The ID of the configured Superset server.
        dataset_name: Name for the virtual dataset.
        database_id: The ID of the database.
        sql: The SQL query for the virtual dataset.
        schema: Optional schema name.
        description: Optional description.
        default_endpoint_id: Optional endpoint ID.
        columns_json: Optional JSON string of column definitions.
        metrics_json: Optional JSON string of metric definitions.
    Returns:
        JSON string containing the created dataset.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
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
                return f"Error: 'columns_json' is not a valid JSON string."
        if metrics_json:
            try:
                dataset_payload["metrics"] = json.loads(metrics_json)
            except json.JSONDecodeError:
                return f"Error: 'metrics_json' is not a valid JSON string."
        
        endpoint = "/api/v1/dataset/"
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError creating virtual dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return f"Error creating virtual dataset: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating virtual dataset for {server_id}: {e}")
        return f"An unexpected error occurred while creating virtual dataset: {e}"


async def create_dataset(
    manager: ConnectionManager,
    server_id: str,
    table_name: str,
    database_id: int,
    schema: Optional[str] = None,
    owners: Optional[List[int]] = None,
    metrics_json: Optional[str] = None, # JSON string
    columns_json: Optional[str] = None, # JSON string
    sql_expression: Optional[str] = None # For virtual datasets
) -> str:
    """
    Creates a new dataset on a Superset server.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
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
                return f"Error: 'metrics_json' is not a valid JSON string. Please ensure it is a valid JSON array of metric definitions."
        if columns_json:
            try:
                dataset_payload["columns"] = json.loads(columns_json)
            except json.JSONDecodeError:
                return f"Error: 'columns_json' is not a valid JSON string. Please ensure it is a valid JSON array of column definitions."
        if sql_expression:
            dataset_payload["sql_expression"] = sql_expression
        
        # Verify database existence using impl_get_resource
        db_check_result = await impl_get_resource(manager, server_id, "database", database_id)
        if "Error" in db_check_result or "not found" in db_check_result.lower():
            return f"Error: Database with ID '{database_id}' not found on server '{server_id}'. Details: {db_check_result}"

        endpoint = "/api/v1/dataset/"
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()
        
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError creating dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return f"Error creating dataset: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while creating the dataset for {server_id}: {e}")
        return f"An unexpected error occurred while creating the dataset: {e}"

async def get_database_schema(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema_name: Optional[str] = None
) -> str:
    """
    Retrieves the schema (tables and columns) for a specified database.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."

    try:
        # 1. Get database details to determine engine
        db_details_str = await impl_get_resource(manager, server_id, "database", database_id)
        try:
            db_details = json.loads(db_details_str)
        except json.JSONDecodeError:
            return f"Error: Could not parse database details for ID {database_id}: {db_details_str}"

        engine = db_details.get("result", {}).get("backend") # 'postgresql', 'mysql', 'presto', etc.
        if not engine:
            return f"Error: Could not determine database engine for ID {database_id}. Details: {db_details_str}"

        schema_info = {
            "database_id": database_id,
            "database_name": db_details.get("result", {}).get("database_name"),
            "engine": engine,
            "tables": []
        }

        # Define SQL queries based on engine
        table_query = ""
        column_query_template = ""

        if engine == "postgresql":
            table_query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_name if schema_name else 'public'}'
                AND table_type = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = '{schema_name if schema_name else 'public'}'
                AND table_name = '{{table_name}}'
                ORDER BY ordinal_position;
            """
        elif engine == "mysql":
            table_query = f"""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = '{schema_name if schema_name else db_details.get("result", {}).get("database_name")}'
                AND table_type = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = '{schema_name if schema_name else db_details.get("result", {}).get("database_name")}'
                AND table_name = '{{table_name}}'
                ORDER BY ordinal_position;
            """
        elif engine == "mssql":
            table_query = f"""
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = '{schema_name if schema_name else 'dbo'}'
                AND TABLE_TYPE = 'BASE TABLE';
            """
            column_query_template = f"""
                SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = '{schema_name if schema_name else 'dbo'}'
                AND TABLE_NAME = '{{table_name}}'
                ORDER BY ORDINAL_POSITION;
            """
        else:
            return f"Error: Database engine '{engine}' is not supported for automatic schema extraction via information_schema."

        # 2. Get table names
        logger.info(f"Executing table query for {server_id}/{database_id}: {table_query}")
        table_query_res = await sqllab_execute_query(manager, server_id, database_id, table_query, schema=schema_name)
        table_query_json = json.loads(table_query_res)
        table_client_id = table_query_json.get("result", {}).get("query", {}).get("client_id")
        if not table_client_id:
            return f"Error: Failed to execute table query or get client_id: {table_query_res}"

        # Wait for results and get them
        await asyncio.sleep(2) # Give Superset a moment to process
        table_results_res = await sqllab_get_query_results(manager, server_id, table_client_id)
        table_results_json = json.loads(table_results_res)
        table_names = [row["table_name"] for row in table_results_json.get("data", [])] if "data" in table_results_json else []

        if not table_names:
            return f"No tables found in database ID {database_id}, schema '{schema_name if schema_name else 'default'}'."

        # 3. Get columns for each table
        for table_name in table_names:
            columns = []
            current_column_query = column_query_template.format(table_name=table_name)
            logger.info(f"Executing column query for {table_name}: {current_column_query}")
            column_query_res = await sqllab_execute_query(manager, server_id, database_id, current_column_query, schema=schema_name)
            column_query_json = json.loads(column_query_res)
            column_client_id = column_query_json.get("result", {}).get("query", {}).get("client_id")
            
            if column_client_id:
                await asyncio.sleep(2) # Give Superset a moment
                column_results_res = await sqllab_get_query_results(manager, server_id, column_client_id)
                column_results_json = json.loads(column_results_res)
                columns = column_results_json.get("data", [])

            schema_info["tables"].append({
                "table_name": table_name,
                "columns": columns
            })
        
        return json.dumps(schema_info, indent=2)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError fetching database schema for {server_id}: {e.response.status_code} - {e.response.text}")
        return f"Error fetching database schema: {e.response.status_code} - {e.response.text}"
    except json.JSONDecodeError as e:
        return f"Error parsing JSON response: {e}"
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching database schema for {server_id}: {e}")
        return f"An unexpected error occurred while fetching database schema: {e}"
