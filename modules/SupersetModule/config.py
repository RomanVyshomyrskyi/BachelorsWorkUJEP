"""Configuration dataclasses for Superset server connections and runtime contexts.

This module defines the data structures used to hold Superset server connection
parameters and the runtime context that includes authentication state and HTTP client instances.
"""
from dataclasses import dataclass
from typing import Optional
import httpx


@dataclass
class SupersetServerConfig:
    """Configuration for a single Superset server connection.

    Controls which authentication method to use, how credentials are resolved
    (directly from config or environment variables), and optional cookie file
    paths for cookie-based authentication.

    Attributes:
        base_url: The direct Superset server URL (e.g., "https://superset.example.com").
            Takes precedence over base_url_env if both are provided.
        base_url_env: Environment variable name containing the Superset server URL.
            Used when the URL should be loaded from the environment rather than hardcoded.
        auth_method: Authentication method to use. Supported values are "db" (default
            Superset DB auth), "keycloak" (OIDC via Keycloak), "cookie" (session cookie),
            and "cookie_http_auth" (cookie with HTTP Basic Auth to protect Superset).
        username: Direct username credential for "db" auth provider.
        password: Direct password credential for "db" auth provider.
        username_env: Environment variable name containing the username.
            Overrides direct username if set.
        password_env: Environment variable name containing the password.
            Overrides direct password if set.
        provider: Superset auth provider name (default "db"). Passed to the login
            endpoint to select the authentication backend.
        token_url: Direct URL for Keycloak token endpoint (e.g., "https://keycloak.com/realms/.../protocol/openid-connect/token").
        token_url_env: Environment variable name containing the Keycloak token URL.
            Overrides direct token_url if set.
        client_id_env: Environment variable name containing the Keycloak client ID.
        client_secret_env: Environment variable name containing the Keycloak client secret.
        keycloak_username_env: Environment variable name containing the Keycloak resource user's username.
        keycloak_password_env: Environment variable name containing the Keycloak resource user's password.
        cookie_file_path: File system path to a session cookie file for cookie-based auth.
            If relative, resolved against the config directory.
        http_username: HTTP Basic Auth username used to protect the Superset instance itself.
            Used when auth_method is "cookie_http_auth".
        http_password: HTTP Basic Auth password used to protect the Superset instance itself.
            Used when auth_method is "cookie_http_auth".
    """
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
    """Runtime context for an active Superset server connection.

    Holds the resolved configuration, an asynchronous HTTP client, the current
    authentication token state, and metadata needed for token persistence.
    This context is created per server_id by the ConnectionManager and passed
    to all API operations.

    Attributes:
        config: The SupersetServerConfig instance defining connection parameters.
        client: An httpx.AsyncClient pre-configured with the server's base URL
            and ready for authenticated API requests.
        server_id: Unique identifier for this Superset server configuration,
            used as a key in the ConnectionManager's context store.
        access_token: OAuth2/Bearer access token received after authentication.
            Cleared and refreshed on 401 responses.
        csrf_token: Cross-Site Request Forgery token fetched from Superset's
            CSRF endpoint, automatically attached to POST/PUT/DELETE requests.
        session_cookie: Raw session cookie string for cookie-based authentication.
            Used when auth_method is "cookie" or "cookie_http_auth".
        token_path: File system path where the access token is persisted to disk
            for reuse across sessions. Loaded automatically on startup if valid.
    """
    config: SupersetServerConfig
    client: httpx.AsyncClient
    server_id: str
    access_token: Optional[str] = None
    csrf_token: Optional[str] = None
    session_cookie: Optional[str] = None
    token_path: Optional[str] = None
