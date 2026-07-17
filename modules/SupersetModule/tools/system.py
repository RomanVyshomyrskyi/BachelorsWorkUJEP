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
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        endpoint = "/api/v1/metadata/"
        params = {}
        if model_type:
            params["include"] = model_type

        return await impl_superset_api(
            manager, server_id, "GET", endpoint, params=json.dumps(params) if params else None
        )
    except Exception as e:
        return ServerError(f"Error getting schema: {e}", details=str(e)).to_json()


async def get_instance_info(manager: ConnectionManager, server_id: str) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        user_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/me/")
        if isinstance(user_info, str) and user_info.startswith("Error"):
            return ServerError(f"Error getting instance info: {user_info}").to_json()

        try:
            feature_info = await impl_superset_api(manager, server_id, "GET", "/api/v1/feature-features/")
            if isinstance(feature_info, str) and feature_info.startswith("Error"):
                feature_info = '{"result": {}}'
        except Exception:
            feature_info = '{"result": {}}'

        result = {
            "user": json.loads(user_info),
            "features": json.loads(feature_info)
        }

        return json.dumps(result, indent=2)
    except Exception as e:
        return ServerError(f"Error getting instance info: {e}", details=str(e)).to_json()


async def health_check(manager: ConnectionManager, server_id: str) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        return ServerError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        resp = await execute_request(ctx, "GET", "/api/v1/health/")
        status = "healthy" if resp.status_code == 200 else "degraded"
        return json.dumps({
            "status": status,
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "authenticated": ctx.access_token is not None or ctx.session_cookie is not None,
            "status_code": resp.status_code,
        }, indent=2)
    except httpx.HTTPStatusError as e:
        return json.dumps({
            "status": "unhealthy",
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "error": f"HTTP {e.response.status_code}",
            "status_code": e.response.status_code,
        }, indent=2)
    except Exception as e:
        return json.dumps({
            "status": "unreachable",
            "server_id": server_id,
            "base_url": ctx.config.base_url,
            "error": str(e),
        }, indent=2)
