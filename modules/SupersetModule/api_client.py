"""Asynchronous HTTP client utilities and authentication logic for Superset API interactions.

This module provides:
- JWT token parsing and expiration checking utilities
- CSRF token fetching
- Multiple authentication methods (DB, Keycloak, Cookie, Cookie+HTTP Auth)
- Automatic token refresh on 401 responses
- HTTP request execution with metrics collection
- Token persistence to disk for cross-session reuse

All functions accept a SupersetContext object which contains the resolved
configuration, HTTP client, and authentication state.
"""
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
    """Parse JWT token payload without verification to check expiration.

    Decodes the middle segment of a JWT (Base64Url-encoded JSON) to extract
    claims such as 'exp' (expiration time). This is used to determine whether
    a cached token is still valid without making network requests.

    Args:
        token: A complete JWT string in the format "header.payload.signature".

    Returns:
        Dictionary of decoded JWT claims if parsing succeeds,
        None if the token format is invalid or decoding fails.
    """
    try:
        # Split the JWT into its three base64url components
        parts = token.split(".")
        if len(parts) != 3:
            return None
        import base64 as b64

        # Extract the middle (payload) segment and fix base64 padding
        payload = parts[1]
        padding = 4 - len(payload) % 4
        if padding != 4:
            payload += "=" * padding
        # Decode the base64url-encoded JSON payload to a Python dict
        decoded = b64.b64decode(payload)
        return json.loads(decoded)
    except Exception:
        # Return None for any parsing or decoding failure
        return None


def _is_token_expired(token: str, buffer_seconds: int = 60) -> bool:
    """Check if JWT token is expired, with an optional safety buffer.

    Parses the token's 'exp' claim and compares it against the current time,
    subtracting the buffer to proactively refresh tokens before they actually
    expire. This prevents 401 errors from tokens that expire between API calls.

    Args:
        token: JWT access token string to check.
        buffer_seconds: Seconds before actual expiration to consider the token
            as expired. Defaults to 60 (1 minute). Reduces the chance of
            receiving 401 responses due to clock skew or network latency.

    Returns:
        True if the token is expired or will expire within the buffer period,
        or if the token is invalid/unparseable. False if the token is still
        valid beyond the buffer window. Returns True if token is None/empty.
    """
    # Return True (expired) if no token was provided
    if not token:
        return True
    # Decode the JWT payload to extract expiration information
    payload = _parse_jwt_payload(token)
    if not payload:
        # Cannot determine expiration without a valid payload, treat as expired
        return True
    # Extract the 'exp' (expiration timestamp) claim from the payload
    exp = payload.get("exp")
    if not exp:
        # No expiration claim found, assume the token is still valid
        return False
    # Compare current time against expiration minus the safety buffer
    return time.time() >= (exp - buffer_seconds)


async def _get_csrf_token(ctx: SupersetContext):
    """Fetch and store the CSRF token from Superset's security API.

    Makes a GET request to /api/v1/security/csrf_token/ to retrieve the current
    CSRF token, then updates the HTTP client's default headers to include it
    for all subsequent requests. This is required for state-changing operations
    (POST, PUT, DELETE) in Superset.

    Args:
        ctx: SupersetContext containing the HTTP client and storage for the
            csrf_token attribute where the fetched token will be saved.
    """
    try:
        # Fetch the current CSRF token from Superset's security endpoint
        response = await ctx.client.get("/api/v1/security/csrf_token/")
        response.raise_for_status()
        # Extract the token from the JSON response
        data = response.json()
        ctx.csrf_token = data.get("result")
        if ctx.csrf_token:
            # Update headers immediately so all subsequent requests include the CSRF token
            ctx.client.headers.update({"X-CSRFToken": ctx.csrf_token})
    except Exception as e:
        # Log warning but don't fail - CSRF token may be optional for some operations
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
            For 'db': username and password must be provided.
            For 'keycloak': token_url, client_id, client_secret, username, and
                password must all be resolvable from environment variables.
        httpx.HTTPStatusError: If the authentication request returns a
            non-2xx HTTP status code.

    Coroutine: Returns Coroutine[SupersetContext, None, Optional[str]]
    """
    config = ctx.config

    # Handle default Superset database authentication
    if config.auth_method == "db":
        # Validate that both username and password are available for DB auth
        if not config.username or not config.password:
            raise ValueError(f"Username and password required for 'db' auth on {ctx.server_id}")

        # POST credentials to Superset's login API endpoint
        resp = await ctx.client.post("/api/v1/security/login", json={
            "username": config.username,
            "password": config.password,
            "provider": config.provider,
            "refresh": True
        })
        resp.raise_for_status()
        # Extract and return the access token from the response
        return resp.json().get("access_token")

    # Handle Keycloak OIDC authentication (Resource Owner Password Credentials flow)
    elif config.auth_method == "keycloak":
        # Resolve the Keycloak token URL from direct config or environment variable
        token_url = config.token_url
        if config.token_url_env:
            token_url = os.getenv(config.token_url_env)

        # Load Keycloak client credentials and user credentials from environment
        client_id = os.getenv(config.client_id_env) if config.client_id_env else None
        client_secret = os.getenv(config.client_secret_env) if config.client_secret_env else None
        username = os.getenv(config.keycloak_username_env) if config.keycloak_username_env else None
        password = os.getenv(config.keycloak_password_env) if config.keycloak_password_env else None

        # Validate that all required Keycloak configuration is present
        if not all([token_url, client_id, client_secret, username, password]):
            raise ValueError("Missing Keycloak env vars configuration")

        # Create a separate HTTP client for Keycloak (isolated from Superset client)
        async with httpx.AsyncClient() as kc_client:
            # POST to Keycloak token endpoint with resource owner password credentials
            resp = await kc_client.post(token_url, data={
                "grant_type": "password",
                "client_id": client_id,
                "client_secret": client_secret,
                "username": username,
                "password": password,
                "scope": "openid offline_access"
            })
            resp.raise_for_status()
            # Extract and return the access token from Keycloak response
            return resp.json().get("access_token")

    # Unsupported auth method - return None (caller should handle)
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

    # Handle token-based authentication methods (DB and Keycloak)
    if config.auth_method in ["db", "keycloak"]:
        # Obtain the access token via the appropriate authentication flow
        token = await get_access_token(ctx)
        if token:
            # Store the token in context and set the Authorization Bearer header
            ctx.access_token = token
            ctx.client.headers.update({"Authorization": f"Bearer {token}"})

            # Persist the access token to disk for cross-session reuse
            if ctx.token_path:
                try:
                    with open(ctx.token_path, 'w') as f:
                        f.write(token)
                    logger.info(f"Saved access token for {ctx.server_id} to disk.")
                except Exception as e:
                    logger.warning(f"Failed to save token for {ctx.server_id}: {e}")

            # Fetch and set the CSRF token for state-changing requests
            await _get_csrf_token(ctx)

    # Handle cookie-based authentication methods
    elif config.auth_method in ["cookie", "cookie_http_auth"]:
        # Add HTTP Basic Auth header if this is cookie_http_auth mode
        if config.http_username:
            creds = f"{config.http_username}:{config.http_password}"
            b64_creds = base64.b64encode(creds.encode()).decode()
            ctx.client.headers.update({"Authorization": f"Basic {b64_creds}"})

        # Load the session cookie from the configured file path
        if config.cookie_file_path and os.path.exists(config.cookie_file_path):
            with open(config.cookie_file_path, 'r') as f:
                cookie = f.read().strip()
            ctx.session_cookie = cookie
            # Set the session cookie header for authenticated requests
            ctx.client.headers.update({"Cookie": f"session={cookie}"})
            # Fetch CSRF token to enable state-changing operations with cookie auth
            await _get_csrf_token(ctx)
        else:
            # Fail if cookie auth is configured but the cookie file is missing
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
    # Case 1: Have an in-memory token - check if it's expired
    if ctx.access_token:
        # Token is expired or nearing expiration, clear it and re-authenticate
        if _is_token_expired(ctx.access_token):
            logger.info(f"Token expired for {ctx.server_id}. Re-authenticating...")
            ctx.access_token = None
        else:
            # Token is still valid within the buffer window, no action needed
            return

    # Case 2: Have a session cookie (cookie auth doesn't expire in the same way)
    if ctx.session_cookie:
        # Cookie-based auth doesn't require JWT expiration checks
        return

    # Case 3: Try loading token from disk cache
    if ctx.token_path and os.path.exists(ctx.token_path):
        try:
            with open(ctx.token_path, 'r') as f:
                token = f.read().strip()
            if token:
                # Validate the disk token's expiration before using it
                if not _is_token_expired(token):
                    ctx.access_token = token
                    ctx.client.headers.update({"Authorization": f"Bearer {token}"})
                    logger.info(f"Loaded valid access token for {ctx.server_id} from disk.")
                    # Fetch CSRF token to enable state-changing operations
                    await _get_csrf_token(ctx)
                    return
                else:
                    # Disk token exists but is expired, proceed to fresh auth
                    logger.info(f"Disk token expired for {ctx.server_id}. Re-authenticating...")
        except Exception as e:
            logger.warning(f"Failed to load token from disk for {ctx.server_id}: {e}")

    # Case 4: Fresh authentication - no valid token found anywhere
    await authenticate(ctx)


async def execute_request(
     ctx: SupersetContext,
     method: str,
     endpoint: str,
     **kwargs
 ) -> httpx.Response:
    """Execute an HTTP request with automatic token refresh on 401.

    Handles the full request lifecycle: ensure authentication, execute the request,
    detect 401 Unauthorized responses (triggering token refresh and retry), collect
    Prometheus metrics, and propagate exceptions. On 401, clears all cached credentials,
    re-authenticates from scratch, and retries the original request exactly once.

    Args:
        ctx: SupersetContext containing the authenticated HTTP client and
            authentication state to use for the request.
        method: HTTP method for the request (GET, POST, PUT, DELETE, PATCH).
        endpoint: API endpoint path relative to the server's base URL
            (e.g., "/api/v1/chart/").
        **kwargs: Additional keyword arguments passed directly to httpx.AsyncClient.request(),
            such as json=, data=, params=, headers=.

    Returns:
        httpx.Response object containing the server's response with status_code,
        headers, and content attributes.

    Raises:
        httpx.HTTPStatusError: If the response status code indicates an error
            (4xx or 5xx) after the retry attempt.
        httpx.RequestError: If a network-level error occurs during the request.

    Coroutine: Returns Coroutine[SupersetContext, None, httpx.Response]
    """
    mc = get_metrics()
    start_time = time.monotonic()

    # Ensure we have valid authentication before making the request
    await ensure_auth(ctx)

    try:
        # Execute the HTTP request with the provided method, endpoint, and extra kwargs
        resp = await ctx.client.request(method, endpoint, **kwargs)

        # Handle 401 Unauthorized by clearing credentials and retrying once
        if resp.status_code == 401:
            logger.info(f"401 received for {ctx.server_id} on {method} {endpoint}. Re-authenticating...")
            # Clear all cached authentication state to force fresh authentication
            ctx.access_token = None
            ctx.session_cookie = None
            await ensure_auth(ctx)

            # Retry the original request with fresh authentication
            resp = await ctx.client.request(method, endpoint, **kwargs)

        # Record request duration and success/failure in Prometheus metrics
        elapsed = time.monotonic() - start_time
        status = str(resp.status_code)
        mc.api_requests.labels(method=method, endpoint=endpoint, status_code=status).inc()

        return resp

    except httpx.HTTPStatusError as e:
        # Record metrics for HTTP error responses before re-raising
        elapsed = time.monotonic() - start_time
        status = str(e.response.status_code)
        mc.api_requests.labels(method=method, endpoint=endpoint, status_code=status).inc()
        raise
    except Exception as e:
        # Record metrics for network-level errors and log the full error details
        elapsed = time.monotonic() - start_time
        mc.api_requests.labels(method=method, endpoint=endpoint, status_code="error").inc()
        logger.error(f"Request failed for {ctx.server_id} on {method} {endpoint}: {e}")
        raise
