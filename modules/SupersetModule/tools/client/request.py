"""HTTP request execution with metrics collection for Superset API.

This module provides:
- HTTP request execution with automatic token refresh on 401
- Prometheus metrics collection for API requests
- Exception handling and error logging
"""

import logging
import time
import httpx
from modules.SupersetModule.config import SupersetContext
from modules.SupersetModule.tools.client.auth import ensure_auth
from modules.metrics import get_metrics

logger = logging.getLogger(__name__)


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
