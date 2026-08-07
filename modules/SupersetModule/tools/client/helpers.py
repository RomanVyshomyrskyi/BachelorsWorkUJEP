"""JWT token parsing and expiration checking utilities.

This module provides helper functions for JWT token validation:
- Parsing JWT payloads without verification
- Checking token expiration with configurable safety buffer
"""

import json
import time


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
    if not token:
        return True
    payload = _parse_jwt_payload(token)
    if not payload:
        return True
    exp = payload.get("exp")
    if not exp:
        return False
    return time.time() >= (exp - buffer_seconds)
