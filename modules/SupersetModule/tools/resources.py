from typing import Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import RESOURCE_ENDPOINTS
from modules.SupersetModule.tools.general import impl_superset_api
from modules.metrics import get_metrics

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
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
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
    Lists dashboards to get their IDs.
    """
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
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
    mc = get_metrics()
    start_time = __import__('time').monotonic()
    try:
        result = await impl_get_resource(manager, server_id, resource_type, resource_id)
        elapsed = __import__('time').monotonic() - start_time
        mc.tool_calls.labels(tool=f"superset_get_{resource_type}", status="success").inc()
        mc.tool_duration.labels(tool=f"superset_get_{resource_type}").observe(elapsed)
        return result
    except Exception as e:
        mc.tool_calls.labels(tool=f"superset_get_{resource_type}", status="error").inc()
        raise
