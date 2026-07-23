"""
Generic resource management tools for Apache Superset MCP integration.

Provides generic CRUD operations for any Superset resource type (charts,
dashboards, datasets, databases, users, etc.) through a unified interface.
Also includes a resource type registry that maps resource names to API endpoints.

MCP Tools Provided:
    - superset_list_resource_types: List all available resource types
    - superset_list_resources: List resources of any type
    - superset_list_charts: List all charts
    - superset_list_dashboards: List all dashboards
    - superset_get_resource: Get details for any resource by ID
"""

from typing import Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import RESOURCE_ENDPOINTS
from modules.SupersetModule.tools.general import impl_superset_api
from modules.metrics import get_metrics

async def list_resource_types() -> str:
    """
    MCP Tool: superset_list_resource_types - List all available resource types.

    Returns a list of all resource types that can be managed through the
    Superset MCP tools. These correspond to Superset API resource endpoints
    (charts, dashboards, datasets, databases, users, etc.).

    Returns:
        String listing all available resource types, one per line with '- ' prefix.
        Each line corresponds to a resource that can be queried with list_resources.
    """
    # Sort resource type keys alphabetically for consistent display
    keys = sorted(list(RESOURCE_ENDPOINTS.keys()))
    return "Available Resource Types:\n" + "\n".join(f"- {k}" for k in keys)

async def impl_list_resources(manager: ConnectionManager, server_id: str, resource_type: str) -> str:
    """
    Internal: List all resources of a given type from Superset.

    Resolves the API endpoint for the given resource type (using RESOURCE_ENDPOINTS
    mapping or a default pattern) and fetches the full list.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        resource_type: The type name (e.g., 'chart', 'dashboard') used to resolve the endpoint.

    Returns:
        JSON string containing the list of resources from the Superset API.
    """
    # Resolve the API endpoint from the resource type mapping, falling back to a default pattern
    base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
    return await impl_superset_api(manager, server_id, "GET", base)

async def list_resources(manager: ConnectionManager, server_id: str, resource_type: str) -> str:
    """
    MCP Tool: superset_list_resources - Lists resources of a specific type.

    Fetches all resources of a given type from Superset. Works with any resource
    type registered in RESOURCE_ENDPOINTS (charts, dashboards, datasets, databases,
    users, etc.). Returns the full paginated list from the API.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        resource_type: The type of resources to list (e.g., 'chart', 'dashboard',
            'dataset', 'database', 'user'). Must be one of the registered resource types.

    Returns:
        JSON string containing the list of resources from the Superset API.
    """
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
        # Delegate to the internal list helper with metrics tracking
        result = await impl_list_resources(manager, server_id, resource_type)
        elapsed = __import__('time').monotonic() - start_time
        mc.tool_calls.labels(tool=f"superset_list_{resource_type}", status="success").inc()
        mc.tool_duration.labels(tool=f"superset_list_{resource_type}").observe(elapsed)
        return result
    except Exception as e:
        mc.tool_calls.labels(tool=f"superset_list_{resource_type}", status="error").inc()
        raise

async def list_dashboards(manager: ConnectionManager, server_id: str) -> str:
    """
    MCP Tool: superset_list_dashboards - Lists all dashboards on a Superset server.

    Shortcut for list_resources with resource_type='dashboard'. Returns the
    complete list of dashboards including their IDs, titles, and slugs.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.

    Returns:
        JSON string containing the list of dashboards from GET /api/v1/dashboard/.
    """
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
        # Shortcut delegate to the internal list helper specifically for dashboards
        result = await impl_list_resources(manager, server_id, "dashboard")
        elapsed = __import__('time').monotonic() - start_time
        mc.tool_calls.labels(tool="superset_list_dashboards", status="success").inc()
        mc.tool_duration.labels(tool="superset_list_dashboards").observe(elapsed)
        return result
    except Exception as e:
        mc.tool_calls.labels(tool="superset_list_dashboards", status="error").inc()
        raise

async def impl_get_resource(
    manager: ConnectionManager,
    server_id: str,
    resource_type: str,
    resource_id: Union[int, str]
) -> str:
    """
    Internal: Fetch a specific resource by type and ID from Superset.

    Looks up the API endpoint for the resource type and makes a GET request
    to fetch the resource details by ID.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        resource_type: The type of resource to fetch (e.g., 'chart', 'dashboard').
        resource_id: The numeric or string ID of the resource.

    Returns:
        JSON string containing the resource details from the Superset API.
    """
    # Resolve the API endpoint from the resource type mapping, then append the resource ID
    base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
    endpoint = f"{base}/{resource_id}"
    return await impl_superset_api(manager, server_id, "GET", endpoint)

async def get_resource(
    manager: ConnectionManager,
    server_id: str,
    resource_type: str,
    resource_id: Union[int, str]
) -> str:
    """
    MCP Tool: superset_get_resource - Gets details for a specific resource by ID.

    Fetches the complete details for any Superset resource by type and ID.
    Works with any resource type registered in RESOURCE_ENDPOINTS.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        resource_type: The type of resource to fetch (e.g., 'chart', 'dashboard').
        resource_id: The numeric or string ID of the specific resource.

    Returns:
        JSON string containing the full resource details from GET /api/v1/{type}/{id}.
    """
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
        # Delegate to the internal get-resource helper with metrics tracking
        result = await impl_get_resource(manager, server_id, resource_type, resource_id)
        elapsed = __import__('time').monotonic() - start_time
        mc.tool_calls.labels(tool=f"superset_get_{resource_type}", status="success").inc()
        mc.tool_duration.labels(tool=f"superset_get_{resource_type}").observe(elapsed)
        return result
    except Exception as e:
        mc.tool_calls.labels(tool=f"superset_get_{resource_type}", status="error").inc()
        raise
