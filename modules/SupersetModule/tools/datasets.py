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
from modules.SupersetModule.exceptions import DatasetError
from modules.SupersetModule.schemas.dataset import DatabaseSchemaResponse

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
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json()

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
                return DatasetError("'columns_json' is not a valid JSON string.", details=columns_json).to_json()
        if metrics_json:
            try:
                dataset_payload["metrics"] = json.loads(metrics_json)
            except json.JSONDecodeError:
                return DatasetError("'metrics_json' is not a valid JSON string.", details=metrics_json).to_json()

        endpoint = "/api/v1/dataset/"
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()

        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError creating virtual dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return DatasetError(
            f"HTTP {e.response.status_code} creating virtual dataset",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        logger.error(f"Unexpected error creating virtual dataset for {server_id}: {e}")
        return DatasetError(f"Unexpected error creating virtual dataset: {e}", details=str(e)).to_json()


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
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json()

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
                return DatasetError("'metrics_json' is not valid JSON.", details=metrics_json).to_json()
        if columns_json:
            try:
                dataset_payload["columns"] = json.loads(columns_json)
            except json.JSONDecodeError:
                return DatasetError("'columns_json' is not valid JSON.", details=columns_json).to_json()
        if sql_expression:
            dataset_payload["sql_expression"] = sql_expression

        db_check_result = await impl_get_resource(manager, server_id, "database", database_id)
        if "Error" in db_check_result or "not found" in db_check_result.lower():
            return DatasetError(f"Database ID '{database_id}' not found", details=db_check_result).to_json()

        endpoint = "/api/v1/dataset/"
        resp = await execute_request(ctx, "POST", endpoint, json=dataset_payload)
        resp.raise_for_status()

        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError creating dataset for {server_id}: {e.response.status_code} - {e.response.text}")
        return DatasetError(
            f"HTTP {e.response.status_code} creating dataset",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        logger.error(f"Unexpected error creating dataset for {server_id}: {e}")
        return DatasetError(f"Unexpected error creating dataset: {e}", details=str(e)).to_json()

async def get_database_schema(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema_name: Optional[str] = None
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatasetError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        db_details_str = await impl_get_resource(manager, server_id, "database", database_id)
        try:
            db_details = json.loads(db_details_str)
        except json.JSONDecodeError:
            return DatasetError(f"Could not parse database details for ID {database_id}", details=db_details_str).to_json()

        engine = db_details.get("result", {}).get("backend")
        if not engine:
            return DatasetError(f"Could not determine database engine for ID {database_id}", details=db_details_str).to_json()

        schema_info = {
            "database_id": database_id,
            "database_name": db_details.get("result", {}).get("database_name"),
            "engine": engine,
            "tables": []
        }

        table_query = ""
        column_query_template = ""

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
        elif engine == "mysql":
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
            return DatasetError(f"Engine '{engine}' not supported for schema extraction").to_json()

        logger.info(f"Executing table query for {server_id}/{database_id}")
        table_query_res = await sqllab_execute_query(manager, server_id, database_id, table_query, schema=schema_name)
        table_query_json = json.loads(table_query_res)
        table_client_id = table_query_json.get("result", {}).get("query", {}).get("client_id")
        if not table_client_id:
            return DatasetError("Failed to execute table query", details=table_query_res).to_json()

        await asyncio.sleep(2)
        table_results_res = await sqllab_get_query_results(manager, server_id, table_client_id)
        table_results_json = json.loads(table_results_res)
        table_names = [row["table_name"] for row in table_results_json.get("data", [])] if "data" in table_results_json else []

        if not table_names:
            return f"No tables found in database ID {database_id}."

        for table_name in table_names:
            columns = []
            current_column_query = column_query_template.format(table_name=table_name)
            logger.info(f"Executing column query for {table_name}")
            column_query_res = await sqllab_execute_query(manager, server_id, database_id, current_column_query, schema=schema_name)
            column_query_json = json.loads(column_query_res)
            column_client_id = column_query_json.get("result", {}).get("query", {}).get("client_id")

            if column_client_id:
                await asyncio.sleep(2)
                column_results_res = await sqllab_get_query_results(manager, server_id, column_client_id)
                column_results_json = json.loads(column_results_res)
                columns = column_results_json.get("data", [])

            schema_info["tables"].append({
                "table_name": table_name,
                "columns": columns
            })

        return json.dumps(schema_info, indent=2)

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTPStatusError fetching database schema for {server_id}: {e.response.status_code}")
        return DatasetError(
            f"HTTP {e.response.status_code} fetching schema",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except json.JSONDecodeError as e:
        return DatasetError(f"JSON parse error: {e}").to_json()
    except Exception as e:
        logger.error(f"Unexpected error fetching database schema for {server_id}: {e}")
        return DatasetError(f"Unexpected error fetching schema: {e}", details=str(e)).to_json()
