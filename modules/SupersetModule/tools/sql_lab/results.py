"""SQL Lab query results retrieval for Superset MCP integration.

Provides sqllab_get_query_results() - fetches results from a previously
executed SQL Lab query using the client_id.
"""

import json
import httpx
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import SqlLabError


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
