import json
from typing import List, Dict, Any, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api


async def get_schema(
    manager: ConnectionManager,
    server_id: str,
    model_type: Optional[str] = None
) -> str:
    """Get schema metadata for chart/dataset/dashboard/database models.
    
    Returns filterable columns, sortable columns, default columns, and
    search columns for list tools. Use this before calling list_* tools
    to discover available filter columns.
    
    Args:
        server_id: The ID of the configured Superset server.
        model_type: Optional type filter ('chart', 'dataset', 'dashboard', 'database').
    Returns:
        JSON string containing schema metadata.
    """
    endpoint = "/api/v1/metadata/"
    params = {}
    if model_type:
        params["include"] = model_type
    
    return await impl_superset_api(
        manager, server_id, "GET", endpoint, params=json.dumps(params) if params else None
    )


async def get_instance_info(manager: ConnectionManager, server_id: str) -> str:
    """Get instance-wide statistics, metadata, and current user identity.
    
    Returns information about the current user, available features,
    and instance metadata. Call this first after connecting to learn
    the user's identity and capabilities.
    
    Args:
        server_id: The ID of the configured Superset server.
    Returns:
        JSON string containing instance information.
    """
    # Get current user info
    user_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/me/")
    
    # Get feature availability
    try:
        feature_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/feature-features/")
    except Exception:
        feature_info = '{"result": {}}'
    
    result = {
        "user": json.loads(user_info),
        "features": json.loads(feature_info)
    }
    
    return json.dumps(result, indent=2)
