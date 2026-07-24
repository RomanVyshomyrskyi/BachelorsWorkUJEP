"""
SQL Lab tools for Apache Superset MCP integration.

Provides tools for executing SQL queries, retrieving results, saving queries,
and generating SQL Lab URLs. These tools enable programmatic data exploration
and SQL execution within the Superset environment.

MCP Tools Provided:
    - superset_sqllab_execute_query: Execute a SQL query and get results
    - superset_sqllab_get_query_results: Retrieve results from a previously executed query
    - superset_save_sql_query: Save a SQL query for later reuse
    - superset_open_sql_lab_with_context: Open SQL Lab UI with pre-filled SQL
"""

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
    """
    MCP Tool: superset_sqllab_execute_query - Execute a SQL query and get results.

    Sends a SQL query to Superset's SQL Lab engine for execution against a specific
    database. Returns the query results as JSON. For long-running queries, use
    sqllab_get_query_results with the returned client_id to fetch results asynchronously.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to execute the query against.
        sql_query: The SQL query string to execute. Must be a valid SELECT statement.
        schema: Optional schema name for databases that support schemas (e.g., PostgreSQL).
        client_id: Optional client ID to track the query. If not provided, Superset
            generates one automatically.
        tab_name: Optional name for the query tab in the SQL Lab UI.

    Returns:
        JSON string containing the query results, metadata (column names, row count),
        and execution details. Returns SqlLabError JSON on failure.

    Example:
        result = await sqllab_execute_query(
            manager, server_id="main", database_id=1,
            sql_query="SELECT * FROM public.sales LIMIT 10"
        )
        # Returns JSON with query results, columns metadata, and client_id for async polling
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_sqllab_execute", status="error").inc()
        mc.record_error(tool="superset_sqllab_execute", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        # Build the SQL Lab execution payload with database ID and SQL query
        sqllab_payload: Dict[str, Any] = {
            "database_id": database_id,
            "sql": sql_query,
        }
        # Attach optional parameters only when provided
        if schema:
            sqllab_payload["schema"] = schema
        if client_id:
            sqllab_payload["client_id"] = client_id
        if tab_name:
            sqllab_payload["tab_name"] = tab_name

        # Execute the SQL query through Superset's SQL Lab API
        endpoint = "/api/v1/sqllab/execute/"
        resp = await execute_request(ctx, "POST", endpoint, json=sqllab_payload)
        resp.raise_for_status()

        # Record success metrics and return formatted JSON response
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
    """
    MCP Tool: superset_sqllab_get_query_results - Retrieve results from a previously executed query.

    Fetches the results of a SQL query that was previously executed via
    sqllab_execute_query. Use the client_id returned from the execute call
    to retrieve the results. This is useful for long-running queries where
    you need to poll for completion.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        client_id: The client ID returned by sqllab_execute_query, used to
            identify the query whose results to fetch.

    Returns:
        JSON string containing the query results (data rows, column metadata,
        row count), or SqlLabError JSON on failure.

    Example:
        result = await sqllab_get_query_results(manager, server_id="main", client_id="abc123-xyz")
        # Returns JSON with data rows and column metadata from the previously executed query
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Fetch query results from Superset using the client_id returned by execute
        endpoint = f"/api/v1/sqllab/results/{client_id}/"
        resp = await execute_request(ctx, "GET", endpoint)
        resp.raise_for_status()

        # Return the formatted JSON results including data rows and metadata
        return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
        # Handle HTTP errors specifically for better diagnostics
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
    """
    MCP Tool: superset_save_sql_query - Save a SQL query for later reuse.

    Saves a SQL query to Superset's Saved Queries library so it can be
    re-executed later from the UI or via API. Saved queries are associated
    with a specific database and can include a description.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database this query targets.
        label: A human-readable name for the saved query.
        sql: The SQL query string to save.
        schema: Optional schema name for the query's database context.
        description: Optional description of what the query does.

    Returns:
        JSON string containing the saved query's details (ID, label, SQL,
        database reference) on success, or SqlLabError JSON on failure.

    Example:
        result = await save_sql_query(
            manager, server_id="main", database_id=1,
            label="Monthly Sales Report", sql="SELECT * FROM public.sales",
            description="Base query for monthly sales analysis"
        )
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_save_sql_query", status="error").inc()
        mc.record_error(tool="superset_save_sql_query", error_message=f"Server '{server_id}' not found.")
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Record start time for performance metrics tracking
    start_time = time.monotonic()
    try:
        # Build the saved query payload with required database, label, and SQL fields
        payload: Dict[str, Any] = {
            "database_id": database_id,
            "label": label,
            "sql": sql,
        }
        # Attach optional fields only when provided
        if schema:
            payload["schema"] = schema
        if description:
            payload["description"] = description

        # POST the saved query to Superset's saved-query API endpoint
        endpoint = "/api/v1/saved-query/"
        resp = await execute_request(ctx, "POST", endpoint, json=payload)
        resp.raise_for_status()

        # Record success metrics and return the saved query details
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
    """
    MCP Tool: superset_open_sql_lab_with_context - Open SQL Lab UI with pre-filled SQL.

    Generates a URL that opens Superset's SQL Lab interface with the database and
    optional SQL query pre-selected/filled. Useful for redirecting users to SQL
    Lab with a specific query ready to execute.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to open SQL Lab for.
        sql: Optional SQL query string to pre-fill in the SQL Lab editor.
        schema: Optional schema name to pre-select in the SQL Lab interface.

    Returns:
        JSON string containing the SQL Lab URL, database_id, sql (if provided),
        and schema (if provided). Returns SqlLabError JSON if the server is not found.

    Example:
        result = await open_sql_lab_with_context(
            manager, server_id="main", database_id=1,
            sql="SELECT * FROM public.sales", schema="public"
        )
        # Returns JSON with a URL that opens SQL Lab pre-filled with the query
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        base_url = ctx.config.base_url.rstrip("/")

        # Build query parameters for the SQL Lab URL, starting with the database ID
        params = f"dbId={database_id}"
        # Append optional SQL and schema query parameters if provided
        if sql:
            params += f"&qtSQL={sql}"
        if schema:
            params += f"&schema={schema}"

        # Construct the final SQL Lab URL with all context parameters
        sql_lab_url = f"{base_url}/sqllab/?{params}"

        # Return the URL and context details as a structured JSON response
        return SqlLabUrlResponse(
            url=sql_lab_url,
            database_id=database_id,
            sql=sql,
            schema=schema,
        ).model_dump_json(indent=2)
    except Exception as e:
        return SqlLabError(f"Unexpected error generating SQL Lab URL: {e}", details=str(e)).to_json()
