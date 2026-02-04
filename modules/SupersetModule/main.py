import os
import sys
import json
import base64
import logging
import httpx
import asyncio
from fastmcp import FastMCP
from dataclasses import dataclass
from typing import Optional, Dict, Any, List, Union
from urllib.parse import urlparse, urlunparse

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

# --- Dataclasses & Models ---

@dataclass
class SupersetServerConfig:
    base_url: Optional[str] = None
    base_url_env: Optional[str] = None
    auth_method: str = "db"
    username: Optional[str] = None
    password: Optional[str] = None
    username_env: Optional[str] = None
    password_env: Optional[str] = None
    provider: Optional[str] = "db"
    token_url: Optional[str] = None
    token_url_env: Optional[str] = None
    client_id_env: Optional[str] = None
    client_secret_env: Optional[str] = None
    keycloak_username_env: Optional[str] = None
    keycloak_password_env: Optional[str] = None
    cookie_file_path: Optional[str] = None
    http_username: Optional[str] = None
    http_password: Optional[str] = None

@dataclass
class SupersetContext:
    config: SupersetServerConfig
    client: httpx.AsyncClient
    server_id: str
    access_token: Optional[str] = None
    csrf_token: Optional[str] = None
    session_cookie: Optional[str] = None
    token_path: Optional[str] = None

# --- Manager Logic ---

class ConnectionManager:
    def __init__(self, config_dir: str):
        self._contexts: Dict[str, SupersetContext] = {}
        self._config_dir = config_dir
        self._token_dir = os.path.join(config_dir, ".tokens")
        os.makedirs(self._token_dir, exist_ok=True)

    def get_token_path(self, server_id: str) -> str:
        return os.path.join(self._token_dir, f".superset_token_{server_id}")

    def load_servers(self, config_filename: str = "servers.json"):
        config_path = os.path.join(self._config_dir, config_filename)
        logger.info(f"Loading server config from {config_path}")
        
        if not os.path.exists(config_path):
            logger.warning(f"Config file {config_path} not found.")
            return

        try:
            with open(config_path, 'r') as f:
                servers_config = json.load(f)

            for server_id, config_data in servers_config.items():
                # Resolve base_url
                base_url = None
                base_url_env = config_data.get("base_url_env")
                if base_url_env:
                    base_url = os.getenv(base_url_env)
                else:
                    base_url = config_data.get("base_url")

                if not base_url:
                    logger.warning(f"Server '{server_id}' missing base_url. Skipping.")
                    continue

                # Handle HTTP Basic Auth in URL
                http_username = None
                http_password = None
                auth_method = config_data.get("auth_method")
                if auth_method == 'cookie_http_auth':
                    parsed_url = urlparse(base_url)
                    if parsed_url.username and parsed_url.password:
                        http_username = parsed_url.username
                        http_password = parsed_url.password
                        base_url = urlunparse(parsed_url._replace(netloc=parsed_url.hostname + (f":{parsed_url.port}" if parsed_url.port else "")))

                config_data['base_url'] = base_url
                config_data['http_username'] = http_username
                config_data['http_password'] = http_password

                # Map username/password from env if needed
                if config_data.get("username_env"):
                    config_data["username"] = os.getenv(config_data["username_env"])
                if config_data.get("password_env"):
                    config_data["password"] = os.getenv(config_data["password_env"])

                config = SupersetServerConfig(**config_data)
                
                # Resolve absolute path for cookies if provided relative
                if config.cookie_file_path and not os.path.isabs(config.cookie_file_path):
                    config.cookie_file_path = os.path.join(self._config_dir, config.cookie_file_path)

                client = httpx.AsyncClient(base_url=config.base_url, timeout=60.0)
                token_path = self.get_token_path(server_id)
                self._contexts[server_id] = SupersetContext(
                    config=config, 
                    client=client, 
                    server_id=server_id, 
                    token_path=token_path
                )
        except Exception as e:
            logger.error(f"Error loading servers: {e}")

    def get_context(self, server_id: str) -> Optional[SupersetContext]:
        if not self._contexts:
            self.load_servers()
        return self._contexts.get(server_id)

    async def close_all(self):
        for ctx in self._contexts.values():
            await ctx.client.aclose()

# --- Auth Logic ---

async def _get_csrf_token(ctx: SupersetContext):
    """Fetches and sets the CSRF token."""
    try:
        response = await ctx.client.get("/api/v1/security/csrf_token/")
        response.raise_for_status()
        data = response.json()
        ctx.csrf_token = data.get("result")
        if ctx.csrf_token:
            # Update headers immediately
            ctx.client.headers.update({"X-CSRFToken": ctx.csrf_token})
    except Exception as e:
        logger.warning(f"Failed to fetch CSRF token for {ctx.server_id}: {e}")

async def get_access_token(ctx: SupersetContext) -> Optional[str]:
    """
    Performs the authentication request to the provider and returns the access token.
    Only applies to 'db' and 'keycloak' auth methods.
    """
    config = ctx.config
    
    if config.auth_method == "db":
        if not config.username or not config.password:
            raise ValueError(f"Username and password required for 'db' auth on {ctx.server_id}")
        
        resp = await ctx.client.post("/api/v1/security/login", json={
            "username": config.username,
            "password": config.password,
            "provider": config.provider,
            "refresh": True
        })
        resp.raise_for_status()
        return resp.json().get("access_token")

    elif config.auth_method == "keycloak":
        token_url = config.token_url
        if config.token_url_env:
            token_url = os.getenv(config.token_url_env)
            
        client_id = os.getenv(config.client_id_env) if config.client_id_env else None
        client_secret = os.getenv(config.client_secret_env) if config.client_secret_env else None
        username = os.getenv(config.keycloak_username_env) if config.keycloak_username_env else None
        password = os.getenv(config.keycloak_password_env) if config.keycloak_password_env else None

        if not all([token_url, client_id, client_secret, username, password]):
             raise ValueError("Missing Keycloak env vars configuration")

        async with httpx.AsyncClient() as kc_client:
            resp = await kc_client.post(token_url, data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
                "scope": "openid offline_access"
            })
            resp.raise_for_status()
            return resp.json().get("access_token")
            
    return None

async def authenticate(ctx: SupersetContext):
    """Authenticates the context based on configuration."""
    config = ctx.config
    
    # 1. DB & Keycloak (Token based)
    if config.auth_method in ["db", "keycloak"]:
        token = await get_access_token(ctx)
        if token:
            ctx.access_token = token
            ctx.client.headers.update({"Authorization": f"Bearer {token}"})
            
            # Save access token if present
            if ctx.token_path:
                try:
                    with open(ctx.token_path, 'w') as f:
                        f.write(token)
                    logger.info(f"Saved access token for {ctx.server_id} to disk.")
                except Exception as e:
                    logger.warning(f"Failed to save token for {ctx.server_id}: {e}")
            
            await _get_csrf_token(ctx)

    # 2. Cookie Auth
    elif config.auth_method in ["cookie", "cookie_http_auth"]:
        # HTTP Basic Auth header if needed
        if config.http_username:
            creds = f"{config.http_username}:{config.http_password}"
            b64_creds = base64.b64encode(creds.encode()).decode()
            ctx.client.headers.update({"Authorization": f"Basic {b64_creds}"})
        
        if config.cookie_file_path and os.path.exists(config.cookie_file_path):
            with open(config.cookie_file_path, 'r') as f:
                cookie = f.read().strip()
            ctx.session_cookie = cookie
            ctx.client.headers.update({"Cookie": f"session={cookie}"})
            await _get_csrf_token(ctx)
        else:
            raise ValueError(f"Cookie file not found for {ctx.server_id}")

async def ensure_auth(ctx: SupersetContext):
    """Ensures authentication headers are present, re-authenticates if necessary."""
    if ctx.access_token or ctx.session_cookie:
        return

    # Try loading token from disk
    if ctx.token_path and os.path.exists(ctx.token_path):
        try:
            with open(ctx.token_path, 'r') as f:
                token = f.read().strip()
            if token:
                ctx.access_token = token
                ctx.client.headers.update({"Authorization": f"Bearer {token}"})
                logger.info(f"Loaded access token for {ctx.server_id} from disk.")
                # Refresh CSRF
                await _get_csrf_token(ctx)
                return
        except Exception as e:
            logger.warning(f"Failed to load token from disk for {ctx.server_id}: {e}")

    await authenticate(ctx)


# --- API Logic ---

async def execute_request(ctx: SupersetContext, method: str, endpoint: str, **kwargs) -> httpx.Response:
    """
    Executes a request with automatic token refresh on 401.
    """
    await ensure_auth(ctx)
    
    try:
        resp = await ctx.client.request(method, endpoint, **kwargs)
        
        # If 401 Unauthorized, try to refresh token and retry ONCE
        if resp.status_code == 401:
            logger.info(f"401 received for {ctx.server_id}. Refreshing token...")
            ctx.access_token = None # Clear cached token
            await ensure_auth(ctx) # Force re-auth
            
            # Update headers for the retry
            # ensure_auth updates ctx.client.headers, but if kwargs contained headers, we might need to merge?
            # Typically ctx.client.headers has the auth.
            
            resp = await ctx.client.request(method, endpoint, **kwargs)
            
        return resp
    except Exception as e:
        logger.error(f"Request failed: {e}")
        raise e

# Map simplified resource names to their API endpoint base
RESOURCE_ENDPOINTS = {
    "advanced_data_type": "/api/v1/advanced_data_type",
    "annotation_layer": "/api/v1/annotation_layer",
    "assets": "/api/v1/assets",
    "async_event": "/api/v1/async_event",
    "available_domains": "/api/v1/available_domains",
    "cachekey": "/api/v1/cachekey",
    "chart": "/api/v1/chart",
    "css_template": "/api/v1/css_template",
    "dashboard": "/api/v1/dashboard",
    "database": "/api/v1/database",
    "dataset": "/api/v1/dataset",
    "datasource": "/api/v1/datasource",
    "embedded_dashboard": "/api/v1/embedded_dashboard",
    "explore": "/api/v1/explore",
    "log": "/api/v1/log",
    "query": "/api/v1/query",
    "saved_query": "/api/v1/saved_query",
    "report": "/api/v1/report",
    "rowlevelsecurity": "/api/v1/rowlevelsecurity",
    "security": "/api/v1/security",
    "sqllab": "/api/v1/sqllab",
    "tag": "/api/v1/tag",
    "user": "/api/v1/user",
}

# Transfer Strategies
# "export_import": Uses /export/ (GET) and /import/ (POST multipart)
# "json_copy": Uses / (GET list) -> /{pk} (GET detail) -> / (POST create json)
TRANSFER_STRATEGY = {
    "chart": "export_import",
    "dashboard": "export_import",
    "database": "export_import",
    "dataset": "export_import",
    "saved_query": "export_import",
    "assets": "export_import",
    
    # Fallback to json_copy for others where feasible
    "annotation_layer": "json_copy",
    "css_template": "json_copy",
    "report": "json_copy",
    "rowlevelsecurity": "json_copy",
}

# --- MCP Registration ---

def register(mcp: FastMCP):
    """Registers Superset tools."""
    
    module_dir = os.path.dirname(__file__)
    manager = ConnectionManager(module_dir)
    manager.load_servers()

    @mcp.tool(name="list_superset_servers")
    def tool_list_servers() -> str:
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

    @mcp.tool(name="superset_server_status")
    async def tool_server_status(server_id: str) -> str:
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

    @mcp.tool(name="superset_available_resource_types")
    def tool_list_resource_types() -> str:
        """
        Lists all available resource types that can be used with `superset_list_resources` 
        and other resource-specific tools.
        """
        keys = sorted(list(RESOURCE_ENDPOINTS.keys()))
        return "Available Resource Types:\n" + "\n".join(f"- {k}" for k in keys)

    async def _impl_superset_api(
        server_id: str,
        method: str,
        endpoint: str,
        json_body: Optional[str] = None,
        params: Optional[str] = None
    ) -> str:
        if method.upper() == "DELETE":
            return "Error: DELETE method is forbidden for safety reasons. 'YOLO mode' is not supported."

        ctx = manager.get_context(server_id)
        if not ctx:
            return f"Error: Server '{server_id}' not found."

        try:
            await ensure_auth(ctx)
            
            data = json.loads(json_body) if json_body else None
            query_params = json.loads(params) if params else None
            
            # Ensure endpoint starts with slash
            if not endpoint.startswith("/"):
                endpoint = "/" + endpoint

            resp = await execute_request(
                ctx,
                method=method.upper(),
                endpoint=endpoint,
                json=data,
                params=query_params
            )
            
            # Try to format JSON output
            try:
                return json.dumps(resp.json(), indent=2)
            except:
                return f"Status: {resp.status_code}\nBody: {resp.text}"

        except Exception as e:
            return f"Error executing request: {e}"

    @mcp.tool(name="superset_api_request")
    async def tool_superset_api(
        server_id: str,
        method: str,
        endpoint: str,
        json_body: Optional[str] = None,
        params: Optional[str] = None
    ) -> str:
        """
        Executes a raw API request against a Superset server.
        Use this to access GET, POST, or PUT methods from the Superset API.
        DELETE operations are strictly forbidden via this tool.
        
        Args:
            server_id: The ID of the configured server.
            method: GET, POST, or PUT.
            endpoint: The API endpoint (e.g., '/api/v1/chart/' or '/api/v1/dashboard/1').
            json_body: Optional JSON string for the request body.
            params: Optional JSON string for query parameters.
        """
        return await _impl_superset_api(server_id, method, endpoint, json_body, params)

    async def _impl_list_resources(server_id: str, resource_type: str) -> str:
        base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
        return await _impl_superset_api(server_id, "GET", base)

    @mcp.tool(name="superset_list_resources")
    async def tool_list_resources(server_id: str, resource_type: str) -> str:
        """
        Lists resources of a specific type (e.g., 'dashboard', 'chart', 'database').
        Wrapper around GET /api/v1/{resource_type}/.
        """
        return await _impl_list_resources(server_id, resource_type)

    @mcp.tool(name="list_dashboards")
    async def tool_list_dashboards(server_id: str) -> str:
        """
        Lists dashboards on a specific server to get their IDs.
        """
        return await _impl_list_resources(server_id, "dashboard")

    async def _impl_get_resource(
        server_id: str,
        resource_type: str,
        resource_id: Union[int, str]
    ) -> str:
        base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
        endpoint = f"{base}/{resource_id}"
        return await _impl_superset_api(server_id, "GET", endpoint)

    @mcp.tool(name="superset_get_resource")
    async def tool_get_resource(
        server_id: str,
        resource_type: str,
        resource_id: Union[int, str]
    ) -> str:
        """
        Gets details for a specific resource by ID.
        Wrapper around GET /api/v1/{resource_type}/{pk}.
        """
        return await _impl_get_resource(server_id, resource_type, resource_id)

    async def _impl_transfer_item(
        source_server_id: str,
        target_server_id: str,
        resource_type: str,
        item_id: Union[int, str]
    ) -> str:
        source_ctx = manager.get_context(source_server_id)
        target_ctx = manager.get_context(target_server_id)

        if not source_ctx or not target_ctx:
            return "Error: Server not found."

        strategy = TRANSFER_STRATEGY.get(resource_type, "json_copy")
        
        try:
            await ensure_auth(source_ctx)
            await ensure_auth(target_ctx)
            
            # Strategy: Export/Import (ZIP)
            if strategy == "export_import":
                # Export
                # Most export endpoints take `q=[id]`
                q_param = json.dumps([item_id])
                endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
                export_url = f"{endpoint_base}/export/"
                
                logger.info(f"Exporting {resource_type} {item_id} from {source_server_id}...")
                export_resp = await execute_request(source_ctx, "GET", export_url, params={"q": q_param})
                
                if export_resp.status_code != 200:
                    return f"Export failed: {export_resp.status_code} - {export_resp.text}"
                
                # Import
                import_url = f"{endpoint_base}/import/"
                file_name = f"export_{resource_type}_{item_id}.zip"
                # Check header for filename if available (content-disposition), else use default
                
                files = {'formData': (file_name, export_resp.content, 'application/zip')}
                data = {'overwrite': 'true', 'passwords': '{}'}
                
                logger.info(f"Importing to {target_server_id}...")
                import_resp = await execute_request(target_ctx, "POST", import_url, files=files, data=data)
                
                if import_resp.status_code not in [200, 201]:
                    return f"Import failed: {import_resp.status_code} - {import_resp.text}"
                
                return f"Successfully transferred {resource_type} {item_id}."

            # Strategy: JSON Copy (Get Detail -> Post Create)
            elif strategy == "json_copy":
                endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
                
                # Get Detail
                detail_url = f"{endpoint_base}/{item_id}"
                get_resp = await execute_request(source_ctx, "GET", detail_url)
                if get_resp.status_code != 200:
                    return f"Failed to get item from source: {get_resp.status_code}"
                
                item_data = get_resp.json().get("result")
                if not item_data:
                    return "Source item data not found in response."

                # Cleanup for Creation
                # We need to remove IDs and other read-only fields to create a new copy
                # This is heuristic and might need adjustment per resource type
                params_to_remove = ['id', 'created_by', 'changed_by', 'created_on', 'changed_on', 'owners']
                payload = {k: v for k, v in item_data.items() if k not in params_to_remove}
                
                # Post Create
                post_url = f"{endpoint_base}/"
                create_resp = await execute_request(target_ctx, "POST", post_url, json=payload)
                
                if create_resp.status_code not in [200, 201]:
                    return f"Failed to create on target: {create_resp.status_code} - {create_resp.text}"
                
                return f"Successfully transferred {resource_type} {item_id} (created new ID)."

            else:
                return f"Unknown transfer strategy for {resource_type}"

        except Exception as e:
            return f"Transfer error: {e}"

    @mcp.tool(name="transfer_dashboard")
    async def tool_transfer_dashboard(
        source_server_id: str,
        target_server_id: str,
        dashboard_id: int
    ) -> str:
        """
        Transfers a Dashboard (and its charts) from a source Superset server to a target Superset server.
        """
        return await _impl_transfer_item(source_server_id, target_server_id, "dashboard", dashboard_id)

    @mcp.tool(name="superset_transfer_item")
    async def tool_transfer_item(
        source_server_id: str,
        target_server_id: str,
        resource_type: str,
        item_id: Union[int, str]
    ) -> str:
        """
        Transfers a specific item (Chart, Dashboard, etc.) from one server to another.
        
        Args:
            source_server_id: ID of source server.
            target_server_id: ID of target server.
            resource_type: Type of resource ('dashboard', 'chart', 'database', 'dataset', 'saved_query', 'annotation_layer', etc.)
            item_id: The ID (pk) of the item to transfer.
        """
        return await _impl_transfer_item(source_server_id, target_server_id, resource_type, item_id)