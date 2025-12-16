import os
import sys
import json
import base64
import logging
import httpx
import asyncio
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from dataclasses import dataclass
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, urlunparse

# --- Logging ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stdout)
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

async def authenticate(ctx: SupersetContext):
    """Authenticates the context based on configuration."""
    config = ctx.config
    
    # 1. DB Auth
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
        token = resp.json().get("access_token")
        ctx.access_token = token
        ctx.client.headers.update({"Authorization": f"Bearer {token}"})
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

    # 3. Keycloak (Simplified)
    elif config.auth_method == "keycloak":
        # Note: Ideally implementation should be full OpenID connect flow, 
        # but here we reuse the logic from the example if possible or just warn.
        # For brevity, assuming token is retrieved externally or implemented similar to example.
        # This implementation mirrors the example's password grant logic.
        
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
            token = resp.json().get("access_token")
            ctx.access_token = token
            ctx.client.headers.update({"Authorization": f"Bearer {token}"})
            await _get_csrf_token(ctx)

async def ensure_auth(ctx: SupersetContext):
    """Ensures authentication headers are present, re-authenticates if necessary."""
    # Simple check: if we have tokens/cookies, assume they might be valid, 
    # but strictly speaking we should just authenticate if missing.
    if not ctx.access_token and not ctx.session_cookie:
        await authenticate(ctx)

# --- MCP Registration ---

def register(mcp: FastMCP):
    """Registers Superset tools."""
    
    # Initialize connection manager in the module scope or lazily
    # Since FastMCP tools are stateless functions, we need a global manager
    # pointing to the module directory.
    module_dir = os.path.dirname(__file__)
    manager = ConnectionManager(module_dir)
    manager.load_servers()

    @mcp.tool(name="list_superset_servers")
    def tool_list_servers() -> str:
        """
        Lists all configured Superset servers available for operations.
        """
        servers = []
        for sid, ctx in manager._contexts.items():
            servers.append(f"- {sid}: {ctx.config.base_url} (Auth: {ctx.config.auth_method})")
        
        if not servers:
            return "No servers configured. Please check servers.json in the module directory."
        
        return "Configured Superset Servers:\n" + "\n".join(servers)

    @mcp.tool(name="transfer_dashboard")
    async def tool_transfer_dashboard(
        source_server_id: str,
        target_server_id: str,
        dashboard_id: int
    ) -> str:
        """
        Transfers a Dashboard (and its charts) from a source Superset server to a target Superset server.
        
        Steps:
        1. Exports the dashboard from source as a ZIP file.
        2. Imports the ZIP file to the target.
        """
        source_ctx = manager.get_context(source_server_id)
        target_ctx = manager.get_context(target_server_id)

        if not source_ctx:
            return f"Error: Source server '{source_server_id}' not found."
        if not target_ctx:
            return f"Error: Target server '{target_server_id}' not found."

        try:
            # 1. Authenticate both
            await ensure_auth(source_ctx)
            await ensure_auth(target_ctx)

            # 2. Export from Source
            # Superset export endpoint: /api/v1/dashboard/export/?q=[id]
            # This returns a ZIP file stream.
            q_param = json.dumps([dashboard_id])
            logger.info(f"Exporting dashboard {dashboard_id} from {source_server_id}...")
            
            export_resp = await source_ctx.client.get(
                "/api/v1/dashboard/export/",
                params={"q": q_param}
            )
            
            if export_resp.status_code != 200:
                return f"Export failed on source: {export_resp.status_code} - {export_resp.text}"
            
            zip_content = export_resp.content
            
            # 3. Import to Target
            # Endpoint: POST /api/v1/dashboard/import/
            # Requires multipart/form-data with 'formData' (file) and 'passwords' (optional json)
            logger.info(f"Importing dashboard to {target_server_id}...")
            
            files = {
                'formData': ('dashboard_export.zip', zip_content, 'application/zip')
            }
            data = {
                'overwrite': 'true', # Usually we want to update if exists
                'passwords': '{}'    # Empty JSON for passwords for now
            }
            
            # Note: CSRF token is already in headers from ensure_auth -> authenticate -> _get_csrf_token
            import_resp = await target_ctx.client.post(
                "/api/v1/dashboard/import/",
                files=files,
                data=data
            )

            if import_resp.status_code not in [200, 201]:
                return f"Import failed on target: {import_resp.status_code} - {import_resp.text}"

            return f"Successfully transferred dashboard {dashboard_id} from {source_server_id} to {target_server_id}. Response: {import_resp.text}"

        except Exception as e:
            return f"An error occurred during transfer: {e}"

    @mcp.tool(name="list_dashboards")
    async def tool_list_dashboards(server_id: str) -> str:
        """
        Lists dashboards on a specific server to get their IDs.
        """
        ctx = manager.get_context(server_id)
        if not ctx:
            return f"Error: Server '{server_id}' not found."
        
        try:
            await ensure_auth(ctx)
            resp = await ctx.client.get("/api/v1/dashboard/")
            resp.raise_for_status()
            data = resp.json()
            
            result_list = data.get("result", [])
            output = [f"Dashboards on {server_id}:"]
            for d in result_list:
                output.append(f"- ID: {d.get('id')}, Title: {d.get('dashboard_title')}, Slug: {d.get('slug')}")
            
            return "\n".join(output)
        except Exception as e:
            return f"Error listing dashboards: {e}"

    @mcp.tool(name="transfer_chart")
    async def tool_transfer_chart(
        source_server_id: str,
        target_server_id: str,
        chart_id: int
    ) -> str:
        """
        Transfers a Chart from source to target.
        """
        source_ctx = manager.get_context(source_server_id)
        target_ctx = manager.get_context(target_server_id)

        if not source_ctx or not target_ctx:
            return "Error: Source or Target server not found."

        try:
            await ensure_auth(source_ctx)
            await ensure_auth(target_ctx)

            # Export
            q_param = json.dumps([chart_id])
            export_resp = await source_ctx.client.get("/api/v1/chart/export/", params={"q": q_param})
            if export_resp.status_code != 200:
                return f"Export failed: {export_resp.text}"
            
            # Import
            files = {'formData': ('chart_export.zip', export_resp.content, 'application/zip')}
            data = {'overwrite': 'true', 'passwords': '{}'}
            
            import_resp = await target_ctx.client.post("/api/v1/chart/import/", files=files, data=data)
            
            if import_resp.status_code not in [200, 201]:
                return f"Import failed: {import_resp.text}"
            
            return f"Chart {chart_id} transferred successfully."

        except Exception as e:
            return f"Error: {e}"
