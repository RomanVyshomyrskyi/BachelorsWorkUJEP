from typing import Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import RESOURCE_ENDPOINTS
from modules.SupersetModule.tools.general import impl_superset_api

async def list_resource_types() -> str:
    """
    Lists all available resource types.
    """
    keys = sorted(list(RESOURCE_ENDPOINTS.keys()))
    return "Available Resource Types:\n" + "\n".join(f"- {k}" for k in keys)

async def impl_list_resources(manager: ConnectionManager, server_id: str, resource_type: str) -> str:
    base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
    return await impl_superset_api(manager, server_id, "GET", base)

async def list_resources(manager: ConnectionManager, server_id: str, resource_type: str) -> str:
    """
    Lists resources of a specific type.
    """
    return await impl_list_resources(manager, server_id, resource_type)

async def list_dashboards(manager: ConnectionManager, server_id: str) -> str:
    """
    Lists dashboards to get their IDs.
    """
    return await impl_list_resources(manager, server_id, "dashboard")

async def impl_get_resource(
    manager: ConnectionManager,
    server_id: str,
    resource_type: str,
    resource_id: Union[int, str]
) -> str:
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
    Gets details for a specific resource by ID.
    """
    return await impl_get_resource(manager, server_id, resource_type, resource_id)
