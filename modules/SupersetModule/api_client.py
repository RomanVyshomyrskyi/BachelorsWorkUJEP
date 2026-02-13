import os
import logging
import base64
import httpx
from typing import Optional
from modules.SupersetModule.config import SupersetContext

logger = logging.getLogger(__name__)

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
