"""
General-purpose API utility functions for Apache Superset MCP integration.

Provides the core API request execution pipeline used by all other Superset tools.
Includes a generic API wrapper for making any Superset API call, with built-in
authentication, error handling, and JSON response formatting.

Functions:
    impl_superset_api: Core API request executor used by all tools.
    superset_api_request: Public wrapper for raw API access.
"""

import json
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request, ensure_auth

async def impl_superset_api(
    manager: ConnectionManager,
    server_id: str,
    method: str,
    endpoint: str,
    json_body: Optional[str] = None,
    params: Optional[str] = None
) -> str:
    """
    Internal: Execute a Superset API request with authentication and error handling.

    This is the core API execution function used by all Superset MCP tools.
    It handles authentication, request execution, and response formatting.
    DELETE requests are blocked for safety reasons.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        method: HTTP method for the request ('GET', 'POST', 'PUT', etc.).
            DELETE is not allowed.
        endpoint: The Superset API endpoint path (e.g., '/api/v1/chart/').
            Will be prefixed with '/' if not already present.
        json_body: Optional JSON string of the request body for POST/PUT requests.
        params: Optional JSON string of query parameters to append to the URL.

    Returns:
        JSON-formatted string of the API response on success, or an error message
        string on failure. For non-JSON responses, returns a formatted string
        with status code and body text.

    Example:
        result = await impl_superset_api(manager, server_id="main", method="GET", endpoint="/api/v1/chart/")
        # Returns JSON-formatted response from the Superset API, or error message string
    """
    # Block DELETE operations for safety — destructive actions are not allowed
    if method.upper() == "DELETE":
        return "Error: DELETE method is forbidden for safety reasons. 'YOLO mode' is not supported."

    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."

    try:
        # Ensure the connection has valid authentication before making the request
        await ensure_auth(ctx)
        
        # Parse optional JSON body and query parameters from string to dict
        data = json.loads(json_body) if json_body else None
        query_params = json.loads(params) if params else None
        
        # Ensure the endpoint starts with a forward slash for proper URL construction
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        # Execute the HTTP request against the Superset API with the given method
        resp = await execute_request(
            ctx,
            method=method.upper(),
            endpoint=endpoint,
            json=data,
            params=query_params
        )
        
        # Try to format the response as pretty-printed JSON, fall back to raw text
        try:
            return json.dumps(resp.json(), indent=2)
        except:
            # Non-JSON responses are returned as status code + raw body text
            return f"Status: {resp.status_code}\nBody: {resp.text}"

    except Exception as e:
        return f"Error executing request: {e}"

async def superset_api_request(
    manager: ConnectionManager,
    server_id: str,
    method: str,
    endpoint: str,
    json_body: Optional[str] = None,
    params: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_api_request - Execute a raw Superset API request.

    Provides direct access to any Superset API endpoint. Useful for operations
    not covered by the specialized tool functions. Be cautious — this bypasses
    most validation and error handling.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        method: HTTP method ('GET', 'POST', 'PUT', etc.). DELETE is blocked.
        endpoint: The API endpoint path (e.g., '/api/v1/chart/').
        json_body: Optional JSON string of the request body.
        params: Optional JSON string of query parameters.

    Returns:
        JSON-formatted API response string on success, or an error message on failure.

    Example:
        result = await superset_api_request(
            manager, server_id="main", method="GET",
            endpoint="/api/v1/chart/", params='{"page_size": 10}'
        )
        # Returns JSON-formatted raw API response for direct access to any Superset endpoint
    """
    # Direct pass-through to the internal API executor — all validation happens there
    return await impl_superset_api(manager, server_id, method, endpoint, json_body, params)
