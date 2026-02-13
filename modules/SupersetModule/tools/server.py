import os
import json
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import authenticate, execute_request

async def list_servers(manager: ConnectionManager) -> str:
    """Lists all configured Superset servers."""
    # Reload config if empty (hot-reload fix)
    if not manager._contexts:
        manager.load_servers()

    servers = []
    for sid, ctx in manager._contexts.items():
        servers.append(f"- {sid}: {ctx.config.base_url} (Auth: {ctx.config.auth_method})")
    
    if not servers:
        # Deep Debugging
        debug_info = []
        config_path = os.path.join(manager._config_dir, "servers.json")
        debug_info.append(f"Config Path: {config_path}")
        if os.path.exists(config_path):
            debug_info.append("File exists.")
            try:
                with open(config_path, 'r') as f:
                    content = f.read()
                    debug_info.append(f"Content length: {len(content)}")
                    json.loads(content)
                    debug_info.append("JSON parsing successful.")
            except Exception as e:
                debug_info.append(f"JSON Error: {e}")
        else:
            debug_info.append("File does NOT exist.")
        
        return f"No servers configured. Debug Info:\n" + "\n".join(debug_info)
        
    return "Configured Superset Servers:\n" + "\n".join(servers)

async def reauthenticate(manager: ConnectionManager, server_id: str) -> str:
    """
    Forces re-authentication with a Superset server.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        # Clear existing token to force a fresh authentication
        ctx.access_token = None
        await authenticate(ctx)
        if ctx.access_token:
            return f"Successfully re-authenticated with server '{server_id}'. New token obtained."
        else:
            return f"Re-authentication failed for server '{server_id}'. Check credentials."
    except Exception as e:
        return f"An error occurred during re-authentication for server '{server_id}': {e}"

async def server_status(manager: ConnectionManager, server_id: str) -> str:
    """
    Checks the status and connectivity of a specific Superset server.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        resp = await execute_request(ctx, "GET", "/api/v1/me/")
        if resp.status_code == 200:
            user_data = resp.json().get("result", {})
            return f"Server '{server_id}' is ONLINE. Authenticated as: {user_data.get('username')}"
        else:
            return f"Server '{server_id}' is REACHABLE but returned status {resp.status_code}: {resp.text}"
    except Exception as e:
        return f"Server '{server_id}' is OFFLINE or error occurred: {e}"
