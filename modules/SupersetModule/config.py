from dataclasses import dataclass
from typing import Optional
import httpx

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
