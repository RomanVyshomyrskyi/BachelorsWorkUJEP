"""Authentication functions for Superset API interactions.

This module provides:
- Token-based authentication (db, keycloak)
- Cookie-based authentication (cookie, cookie_http_auth)
- Token persistence to disk for cross-session reuse
- Automatic token refresh on 401 responses
"""

import os
import logging
import base64
import httpx
import json
from typing import Optional
from modules.SupersetModule.config import SupersetContext
from modules.SupersetModule.tools.client.helpers import _is_token_expired

logger = logging.getLogger(__name__)


async def _get_csrf_token(ctx: SupersetContext):
    """Fetch and store the CSRF token from Superset's security API.

    Makes a GET request to /api/v1/security/csrf_token/ to retrieve the current
    CSRF token, then updates the HTTP client's default headers to include it
    for all subsequent requests. This is required for state-changing operations
    (POST, PUT, DELETE) in Superset.

    Args:
        ctx: SupersetContext containing the HTTP client and storage for the
            csrf_token attribute where the fetched token will be saved.

    Returns:
        None
    """
    try:
        response = await ctx.client.get("/api/v1/security/csrf_token/")
        response.raise_for_status()
        data = response.json()
        ctx.csrf_token = data.get("result")
        if ctx.csrf_token:
            ctx.client.headers.update({"X-CSRFToken": ctx.csrf_token})
    except Exception as e:
        logger.warning(f"Failed to fetch CSRF token for {ctx.server_id}: {e}")


async def get_access_token(ctx: SupersetContext) -> Optional[str]:
    """Perform the authentication request and return the access token.

    Handles both 'db' (default Superset authentication) and 'keycloak' (OIDC
    resource owner password credentials flow) auth methods. For 'db', it POSTs
    credentials to /api/v1/security/login. For 'keycloak', it POSTs to the
    configured Keycloak token endpoint with client credentials and user credentials.

    Args:
        ctx: SupersetContext containing the configuration with auth_method,
            username/password (or their env var references), and Keycloak
            connection details.

    Returns:
        The access token string from the authentication response, or None if
        the auth method is unsupported or the request fails. Returns None for
        cookie-based auth methods (cookie, cookie_http_auth).

    Raises:
        ValueError: If required credentials are missing for the auth method.
        httpx.HTTPStatusError: If the authentication request returns a
            non-2xx HTTP status code.

    Coroutine: Returns Coroutine[SupersetContext, None, Optional[str]]
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
    """Authenticate the context based on its configured auth_method.

    Routes to the appropriate authentication flow based on the server configuration:
    - Token-based auth (db, keycloak): Obtains access token, saves to disk,
      sets Authorization Bearer header, and fetches CSRF token
    - Cookie-based auth (cookie, cookie_http_auth): Loads session cookie from
      file, sets Cookie header, optionally adds HTTP Basic Auth, and fetches CSRF token

    Args:
        ctx: SupersetContext containing the configuration determining which
            auth flow to use, HTTP client for making requests, and storage
            for the access token, session cookie, and CSRF token.

    Raises:
        ValueError: If cookie_file_path is set but the file does not exist on disk.
        ValueError: If required credentials are missing for the configured auth method.

    Coroutine: Returns Coroutine[SupersetContext, None, None]
    """
    config = ctx.config

    if config.auth_method in ["db", "keycloak"]:
        token = await get_access_token(ctx)
        if token:
            ctx.access_token = token
            ctx.client.headers.update({"Authorization": f"Bearer {token}"})

            if ctx.token_path:
                try:
                    with open(ctx.token_path, 'w') as f:
                        f.write(token)
                    logger.info(f"Saved access token for {ctx.server_id} to disk.")
                except Exception as e:
                    logger.warning(f"Failed to save token for {ctx.server_id}: {e}")

            await _get_csrf_token(ctx)

    elif config.auth_method in ["cookie", "cookie_http_auth"]:
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
    """Ensure authentication headers are present with live token expiration check.

    Proactively checks JWT token expiration before API calls and re-authenticates
    if the token is expired or about to expire (60s buffer). This prevents 401 errors
    by refreshing tokens before they actually expire.

    Priority order:
        1. Check active in-memory token for expiration; re-authenticate if expired
        2. Check if session cookie is present (cookie auth doesn't use expiration)
        3. Load token from disk cache and validate expiration before using
        4. Perform fresh authentication if no valid token exists anywhere

    Args:
        ctx: SupersetContext containing authentication state (access_token,
            session_cookie), token persistence path, and HTTP client for
            making authentication requests.

    Coroutine: Returns Coroutine[SupersetContext, None, None]
    """
    if ctx.access_token:
        if _is_token_expired(ctx.access_token):
            logger.info(f"Token expired for {ctx.server_id}. Re-authenticating...")
            ctx.access_token = None
        else:
            return

    if ctx.session_cookie:
        return

    if ctx.token_path and os.path.exists(ctx.token_path):
        try:
            with open(ctx.token_path, 'r') as f:
                token = f.read().strip()
            if token:
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

    await authenticate(ctx)
