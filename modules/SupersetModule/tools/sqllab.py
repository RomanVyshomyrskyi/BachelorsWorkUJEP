import json
import httpx
import time
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import SqlLabError
from modules.SupersetModule.schemas.sqllab import SqlLabUrlResponse
from modules.metrics import get_metrics

async def sqllab_execute_query(
     manager: ConnectionManager,
     server_id: str,
     database_id: int,
     sql_query: str,
     schema: Optional[str] = None,
     client_id: Optional[str] = None,
     tab_name: Optional[str] = None
 ) -> str:
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
         mc.record_error(tool="superset_sqllab_execute", error_message=f"Server '{server_id}' not found.")
         return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

     start_time = time.monotonic()
     try:
         sqllab_payload: Dict[str, Any] = {
             "database_id": database_id,
             "sql": sql_query,
         }
         if schema:
             sqllab_payload["schema"] = schema
         if client_id:
             sqllab_payload["client_id"] = client_id
         if tab_name:
             sqllab_payload["tab_name"] = tab_name

         endpoint = "/api/v1/sqllab/execute/"
         resp = await execute_request(ctx, "POST", endpoint, json=sqllab_payload)
         resp.raise_for_status()

         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_sqllab_execute", status="success").inc()
         mc.tool_duration.labels(tool="superset_sqllab_execute").observe(time.monotonic() - start_time)
         mc.queries_executed.labels(source="sql_lab").inc()
         return json.dumps(resp.json(), indent=2)
     except httpx.HTTPStatusError as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
         mc.record_error(tool="superset_sqllab_execute", error_message=f"HTTP {e.response.status_code} executing SQL", status_code=e.response.status_code)
         return SqlLabError(
             f"HTTP {e.response.status_code} executing SQL",
             status_code=e.response.status_code,
             details=e.response.text,
         ).to_json()
     except Exception as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
         mc.record_error(tool="superset_sqllab_execute", error_message=str(e))
         return SqlLabError(f"Unexpected error executing SQL: {e}", details=str(e)).to_json()

async def sqllab_get_query_results(
    manager: ConnectionManager,
    server_id: str,
    client_id: str
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        endpoint = f"/api/v1/sqllab/results/{client_id}/"
        resp = await execute_request(ctx, "GET", endpoint)
        resp.raise_for_status()

        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        return SqlLabError(
            f"HTTP {e.response.status_code} getting query results",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        return SqlLabError(f"Unexpected error getting query results: {e}", details=str(e)).to_json()


async def save_sql_query(
     manager: ConnectionManager,
     server_id: str,
     database_id: int,
     label: str,
     sql: str,
     schema: Optional[str] = None,
     description: Optional[str] = None
 ) -> str:
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
         mc.record_error(tool="superset_save_sql_query", error_message=f"Server '{server_id}' not found.")
         return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

     start_time = time.monotonic()
     try:
         payload: Dict[str, Any] = {
             "database_id": database_id,
             "label": label,
             "sql": sql,
         }
         if schema:
             payload["schema"] = schema
         if description:
             payload["description"] = description

         endpoint = "/api/v1/saved-query/"
         resp = await execute_request(ctx, "POST", endpoint, json=payload)
         resp.raise_for_status()

         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_save_sql_query", status="success").inc()
         mc.tool_duration.labels(tool="superset_save_sql_query").observe(time.monotonic() - start_time)
         mc.queries_executed.labels(source="saved_query").inc()
         return json.dumps(resp.json(), indent=2)
     except httpx.HTTPStatusError as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
         mc.record_error(tool="superset_save_sql_query", error_message=f"HTTP {e.response.status_code} saving SQL query", status_code=e.response.status_code)
         return SqlLabError(
             f"HTTP {e.response.status_code} saving SQL query",
             status_code=e.response.status_code,
             details=e.response.text,
         ).to_json()
     except Exception as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
         mc.record_error(tool="superset_save_sql_query", error_message=str(e))
         return SqlLabError(f"Unexpected error saving SQL query: {e}", details=str(e)).to_json()


async def open_sql_lab_with_context(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql: Optional[str] = None,
    schema: Optional[str] = None
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        base_url = ctx.config.base_url.rstrip("/")

        params = f"dbId={database_id}"
        if sql:
            params += f"&qtSQL={sql}"
        if schema:
            params += f"&schema={schema}"

        sql_lab_url = f"{base_url}/sqllab/?{params}"

        return SqlLabUrlResponse(
            url=sql_lab_url,
            database_id=database_id,
            sql=sql,
            schema=schema,
        ).model_dump_json(indent=2)
    except Exception as e:
        return SqlLabError(f"Unexpected error generating SQL Lab URL: {e}", details=str(e)).to_json()
