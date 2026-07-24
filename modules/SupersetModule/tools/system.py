"""
System and health check tools for Apache Superset MCP integration.

Provides tools for checking Superset server health, retrieving instance
information (user identity, feature flags), and fetching API schema metadata.

MCP Tools Provided:
    - superset_get_instance_info: Get user info and feature flags for the server
    - superset_health_check: Check server health and connectivity status
    - superset_get_schema: Get API schema metadata for a model type
"""

import json
import httpx
from typing import List, Dict, Any, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import ServerError
from modules.SupersetModule.schemas.common import InstanceInfo, UserInfo, FeatureFlags


async def get_schema(
    manager: ConnectionManager,
    server_id: str,
    model_type: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_get_schema - Get API schema metadata for a model type.

    Fetches metadata about Superset's API schema, including filterable and
    sortable columns for a specific model type. Useful for understanding
    what query parameters and filters are available for a resource type.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        model_type: Optional specific model type to get schema for (e.g., 'chart',
            'dashboard'). If not provided, returns the general API metadata schema.

    Returns:
        JSON string containing the schema metadata from GET /api/v1/metadata/,
        including filterable/sortable columns and available resources.
        Returns ServerError JSON if the server is not found.

    Example:
        result = await get_schema(manager, server_id="main", model_type="chart")
        # Returns JSON with filterable/sortable columns and metadata for charts endpoint
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Build the metadata endpoint with an optional model_type filter parameter
        endpoint = "/api/v1/metadata/"
        params = {}
        if model_type:
            params["include"] = model_type

        # Delegate to the generic API executor to fetch schema metadata
        return await impl_superset_api(
            manager, server_id, "GET", endpoint, params=json.dumps(params) if params else None
        )
    except Exception as e:
        return ServerError(f"Error getting schema: {e}", details=str(e)).to_json()


async def get_instance_info(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_get_instance_info - Get user info and feature flags.

    Fetches information about the current authenticated user and the Superset
    instance's feature flags. Useful for understanding what capabilities are
    available on the current Superset deployment.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.

    Returns:
        JSON string containing user info (from GET /api/v1/me/) and feature flags
        (from GET /api/v1/feature-features/). Returns ServerError JSON on failure.

    Example:
        result = await get_instance_info(manager, server_id="main")
        # Returns JSON with current user identity, roles, and enabled feature flags
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Fetch current user info from the Superset API
        user_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/me/")
        if isinstance(user_info, str) and user_info.startswith("Error"):
            return ServerError(f"Error getting instance info: {user_info}").to_json()

        try:
            # Fetch feature flags — gracefully handle if the endpoint is unavailable
            feature_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/feature-features/")
            if isinstance(feature_info, str) and feature_info.startswith("Error"):
                feature_info = '{"result": {}}'
        except Exception:
            # Fall back to empty feature set if the endpoint fails entirely
            feature_info = '{"result": {}}'

        # Combine user info and feature flags into a single response
        result = {
            "user": json.loads(user_info),
            "features": json.loads(feature_info)
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return ServerError(f"Error getting instance info: {e}", details=str(e)).to_json()


async def health_check(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_health_check - Check server health and connectivity.

    Tests the Superset server's health endpoint and reports the connection
    status, authentication state, and base URL. Useful for verifying that
    the MCP connection is working before attempting other operations.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server to check.

    Returns:
        JSON string containing:
          - status: 'healthy', 'degraded', 'unhealthy', or 'unreachable'
          - server_id: The server ID that was checked
          - base_url: The Superset server's base URL
          - authenticated: Whether the current session is authenticated
          - status_code: HTTP status code from the health check
          - error: Error description if status is not 'healthy'

    Example:
        result = await health_check(manager, server_id="main")
        # Returns JSON with status ("healthy"), authentication state, and base URL
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        # Execute the health check GET request to /api/v1/health/
        resp = await execute_request(ctx, "GET", "/api/v1/health/")
        # Determine health status based on HTTP response code
        status = "healthy" if resp.status_code == 200 else "degraded"
        return json.dumps({
            "status": status,
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "authenticated": ctx.access_token is not None or ctx.session_cookie is not None,
            "status_code": resp.status_code,
        }, indent=2)
    except httpx.HTTPStatusError as e:
        # HTTP error response — server is reachable but unhealthy
        return json.dumps({
            "status": "unhealthy",
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "error": f"HTTP {e.response.status_code}",
            "status_code": e.response.status_code,
        }, indent=2)
    except Exception as e:
        # Connection or other error — server is unreachable
        return json.dumps({
            "status": "unreachable",
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "error": str(e),
        }, indent=2)
