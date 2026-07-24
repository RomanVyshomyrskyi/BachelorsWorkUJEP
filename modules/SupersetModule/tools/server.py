import os
import json
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import authenticate, execute_request

async def list_servers(manager: ConnectionManager) -> str:
    """Lists all configured Superset servers with their base URLs and auth methods.

    Description:
        Reads the internal context store and returns a formatted list of all
        configured servers. If no servers are loaded, triggers a hot-reload
        from the servers.json config file and provides debug information.

    Args:
        manager: The ConnectionManager instance holding server configurations.

    Returns:
        A string listing all configured servers with their IDs, base URLs,
        and authentication methods. Returns debug info if no servers are found.

    Example:
        result = await list_servers(manager)
        # Returns a formatted list of all configured Superset server connections
    """
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
    """Forces re-authentication with a Superset server by clearing cached tokens.

    Description:
        Clears the current access token for the specified server and performs
        a fresh authentication flow (DB login, Keycloak OIDC, or cookie-based).
        The new token is persisted to disk for cross-session reuse.

    Args:
        manager: The ConnectionManager instance holding server configurations.
        server_id: The unique identifier of the Superset server to reauthenticate.

    Returns:
        A status string indicating success with the new token, or an error
        message if the server is not found or authentication fails.

    Example:
        result = await reauthenticate(manager, server_id="main")
        # Returns success confirmation with new token details or error message
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
    """Checks the status and connectivity of a specific Superset server.

    Description:
        Performs a health check by calling ``GET /api/v1/me/`` on the target
        server. If successful, returns the authenticated username. If the
        request fails, reports whether the server is reachable or offline.

    Args:
        manager: The ConnectionManager instance holding server configurations.
        server_id: The unique identifier of the Superset server to check.

    Returns:
        A string indicating the server status (ONLINE with username, REACHABLE
        with HTTP error, or OFFLINE) along with relevant details.

    Example:
        result = await server_status(manager, server_id="main")
        # Returns status like "Server 'main' is ONLINE. Authenticated as: admin"
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
