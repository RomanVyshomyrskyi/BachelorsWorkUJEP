import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse
import httpx

from modules.SupersetModule.config import SupersetServerConfig, SupersetContext

logger = logging.getLogger(__name__)

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
