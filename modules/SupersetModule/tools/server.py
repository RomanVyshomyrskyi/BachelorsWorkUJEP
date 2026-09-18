import os
import json
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import authenticate, execute_request

async def list_servers(manager: ConnectionManager) -> str:
    """Lists all configured Superset servers as a JSON array.
        Reads the internal context store and returns a JSON array of server
        objects with id, name, host, port, and enabled fields.
        If no servers are loaded, triggers a hot-reload from servers.json.

    Args:
        manager: The ConnectionManager instance holding server configurations.

    Returns:
        JSON string containing an array of server objects:
        [{"id": "main", "name": "main", "host": "localhost", "port": 8088, "enabled": true}, ...]

    Examples:
        result = await list_servers(manager)
        # Returns '[{"id": "main", "name": "main", "host": "localhost", "port": 8088, "enabled": true}]'
    """
    # Reload config if empty (hot-reload fix)
    if not manager._contexts:
        manager.load_servers()

    servers = []
    for sid, ctx in manager._contexts.items():
        base_url = ctx.config.base_url
        # Parse host and port from base_url (e.g., "http://localhost:8088/api")
        host = "localhost"
        port = 8088
        if "://" in base_url:
            host_part = base_url.split("://")[1]
            if ":" in host_part:
                host, port_str = host_part.split(":", 1)
                try:
                    port = int(port_str)
                except ValueError:
                    port = 8088
            else:
                host = host_part
        
        servers.append({
            "id": sid,
            "name": sid,
            "host": host,
            "port": port,
            "enabled": True,
        })

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
        
        return json.dumps({"result": [], "debug_info": debug_info})
        
    return json.dumps({"result": servers})

async def reauthenticate(manager: ConnectionManager, server_id: str) -> str:
    """Forces re-authentication with a Superset server by clearing cached tokens.
        Clears the current access token for the specified server and performs
        a fresh authentication flow (DB login, Keycloak OIDC, or cookie-based).
        The new token is persisted to disk for cross-session reuse.

    Args:
        manager: The ConnectionManager instance holding server configurations.
        server_id: The unique identifier of the Superset server to reauthenticate.

    Returns:
        A status string indicating success with the new token, or an error
        message if the server is not found or authentication fails.

    Examples:
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
        Performs a health check by calling ``GET /api/v1/me/`` on the target
        server. If successful, returns the authenticated username. If the
        request fails, reports whether the server is reachable or offline.

    Args:
        manager: The ConnectionManager instance holding server configurations.
        server_id: The unique identifier of the Superset server to check.

    Returns:
        A string indicating the server status (ONLINE with username, REACHABLE
        with HTTP error, or OFFLINE) along with relevant details.

    Examples:
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

async def get_server_configs_json(manager: ConnectionManager) -> str:
    """Returns all configured Superset server IDs as a JSON array.
        Reads the internal context store and returns a JSON array of server IDs
        that are currently loaded and available for use.

    Args:
        manager: The ConnectionManager instance holding server configurations.

    Returns:
        A JSON string containing an array of server ID strings.

    Examples:
        result = await get_server_configs_json(manager)
        # Returns '["prod-superset", "staging-superset"]'
    """
    if not manager._contexts:
        manager.load_servers()

    server_ids = list(manager._contexts.keys())
    return json.dumps(server_ids)

async def get_server_configs_full(manager: ConnectionManager) -> str:
    """Returns all configured Superset server details as a JSON object.
        Reads the internal context store and returns a JSON object mapping
        server IDs to their base URLs. This is useful for frontend clients
        that need to know available servers.

    Args:
        manager: The ConnectionManager instance holding server configurations.

    Returns:
        A JSON string containing an object with server IDs as keys and
        base URLs as values, e.g. '{"prod": "https://superset.example.com"}'

    Examples:
        result = await get_server_configs_full(manager)
        # Returns '{"prod": "https://superset.example.com", "staging": "https://staging.example.com"}'
    """
    if not manager._contexts:
        manager.load_servers()

    configs = {}
    for sid, ctx in manager._contexts.items():
        configs[sid] = {
            "base_url": ctx.config.base_url,
            "auth_method": ctx.config.auth_method,
        }
    return json.dumps(configs)
