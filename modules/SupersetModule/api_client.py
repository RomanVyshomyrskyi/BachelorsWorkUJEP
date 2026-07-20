import os
 import logging
 import base64
 import time
 import json
 import httpx
 from typing import Optional
 from modules.SupersetModule.config import SupersetContext
 from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


def _parse_jwt_payload(token: str) -> dict | None:
    """Parse JWT token payload without verification to check expiration."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        import base64 as b64

        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        decoded = b64.b64decode(payload)
        return json.loads(decoded)
    except Exception:
        return None


def _is_token_expired(token: str, buffer_seconds: int = 60) -> bool:
    """Check if JWT token is expired (with buffer)."""
    if not token:
        return True
    payload = _parse_jwt_payload(token)
    if not payload:
        return True
    exp = payload.get("exp")
    if not exp:
        return False
    return time.time() >= (exp - buffer_seconds)

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
    """Ensures authentication headers are present with live token expiration check.
    
    Proactively checks JWT token expiration before API calls and re-authenticates
    if the token is expired or about to expire (60s buffer). This prevents 401 errors
    by refreshing tokens before they actually expire.
    
    Priority:
    1. Active in-memory token (checked for expiration)
    2. Token loaded from disk (checked for expiration)
    3. Fresh authentication
    """
    # Case 1: Have an in-memory token - check if it's expired
    if ctx.access_token:
        if _is_token_expired(ctx.access_token):
            logger.info(f"Token expired for {ctx.server_id}. Re-authenticating...")
            ctx.access_token = None
        else:
            # Token is still valid
            return

    # Case 2: Have a session cookie (cookie auth doesn't expire in the same way)
    if ctx.session_cookie:
        return

    # Case 3: Try loading token from disk
    if ctx.token_path and os.path.exists(ctx.token_path):
        try:
            with open(ctx.token_path, 'r') as f:
                token = f.read().strip()
            if token:
                # Check if disk token is expired before using it
                if not _is_token_expired(token):
                    ctx.access_token = token
                    ctx.client.headers.update({"Authorization": f"Bearer {token}"})
                    logger.info(f"Loaded valid access token for {ctx.server_id} from disk.")
                    await _get_csrf_token(ctx)
                    return
                else:
                    logger.info(f"Disk token expired for {ctx.server_id}. Re-authenticating...")
        except Exception as e:
            logger.warning(f"Failed to load token from disk for {ctx.server_id}: {e}")

    # Case 4: Fresh authentication
    await authenticate(ctx)


async def execute_request(
     ctx: SupersetContext,
     method: str,
     endpoint: str,
     **kwargs
 ) -> httpx.Response:
     """Executes an HTTP request with automatic token refresh on 401.
     
     If a 401 is received, clears the cached token, forces re-authentication,
     and retries the request once. This handles both expired tokens and
     unexpected authorization failures.
     """
     mc = get_metrics()
     start_time = time.monotonic()
     
     await ensure_auth(ctx)

     try:
         resp = await ctx.client.request(method, endpoint, **kwargs)

         if resp.status_code == 401:
             logger.info(f"401 received for {ctx.server_id} on {method} {endpoint}. Re-authenticating...")
             ctx.access_token = None
             ctx.session_cookie = None
             await ensure_auth(ctx)

             resp = await ctx.client.request(method, endpoint, **kwargs)

         elapsed = time.monotonic() - start_time
         status = str(resp.status_code)
         mc.api_requests.labels(method=method, endpoint=endpoint, status_code=status).inc()

         return resp

     except httpx.HTTPStatusError as e:
         elapsed = time.monotonic() - start_time
         status = str(e.response.status_code)
         mc.api_requests.labels(method=method, endpoint=endpoint, status_code=status).inc()
         raise
     except Exception as e:
         elapsed = time.monotonic() - start_time
         mc.api_requests.labels(method=method, endpoint=endpoint, status_code="error").inc()
         logger.error(f"Request failed for {ctx.server_id} on {method} {endpoint}: {e}")
         raise
