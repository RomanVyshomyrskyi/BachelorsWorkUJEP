"""Manages Superset server connections, authentication contexts, and token lifecycle.

The ConnectionManager is responsible for:
- Loading server configurations from a JSON file
- Resolving environment variable references in configuration values
- Creating and caching httpx.AsyncClient instances per server
- Managing token file paths for persistent authentication across sessions
- Providing lifecycle management (cleanup) for all open connections
"""
import os
import json
import logging
from typing import Dict, Optional
from urllib.parse import urlparse, urlunparse
import httpx

from modules.SupersetModule.config import SupersetServerConfig, SupersetContext

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages Superset server connection contexts and their lifecycle.

    This class loads server configurations from a JSON file, resolves environment
    variable references, creates async HTTP clients, and maintains a dictionary
    of active connection contexts keyed by server_id. It also handles token
    persistence directories and HTTP Basic Auth embedded in URLs.
    """

    def __init__(self, config_dir: str):
        """Initialize the connection manager with a configuration directory path.

        Args:
            config_dir: File system path to the directory containing servers.json
                and token files. Used as the base for resolving all relative paths.
        """
        self._contexts: Dict[str, SupersetContext] = {}
        self._config_dir = config_dir
        self._token_dir = os.path.join(config_dir, ".tokens")
        os.makedirs(self._token_dir, exist_ok=True)

    def get_token_path(self, server_id: str) -> str:
        """Compute the absolute file path for a server's persisted access token.

        Args:
            server_id: Unique identifier of the Superset server.

        Returns:
            Absolute file system path to the token file for this server,
            located in the .tokens subdirectory of the config directory.
        """
        return os.path.join(self._token_dir, f".superset_token_{server_id}")

    def load_servers(self, config_filename: str = "servers.json"):
        """Load and parse server configurations from a JSON file.

        Reads the servers configuration JSON, resolves environment variables
        for base_url, username, and password fields, extracts HTTP Basic Auth
        credentials from URLs when present, and creates SupersetContext objects
        for each valid server. Invalid or incomplete server entries are skipped
        with a warning logged.

        Args:
            config_filename: Name of the JSON file containing server configurations.
                Default is "servers.json". Must be located in the config_dir.
        """
        # Construct the full path to the server configuration JSON file
        config_path = os.path.join(self._config_dir, config_filename)
        logger.info(f"Loading server config from {config_path}")

        # Exit early if the configuration file does not exist
        if not os.path.exists(config_path):
            logger.warning(f"Config file {config_path} not found.")
            return

        try:
            # Read and parse the JSON configuration file
            with open(config_path, 'r') as f:
                servers_config = json.load(f)

            # Process each server entry in the configuration
            for server_id, config_data in servers_config.items():
                # Resolve base_url: check environment variable first, fall back to direct value
                base_url = None
                base_url_env = config_data.get("base_url_env")
                if base_url_env:
                    base_url = os.getenv(base_url_env)
                else:
                    base_url = config_data.get("base_url")

                # Skip servers that have no resolvable base_url
                if not base_url:
                    logger.warning(f"Server '{server_id}' missing base_url. Skipping.")
                    continue

                # Handle HTTP Basic Auth embedded in URL (cookie_http_auth mode)
                # Extract username/password from URL and strip them from the URL string
                http_username = None
                http_password = None
                auth_method = config_data.get("auth_method")
                if auth_method == 'cookie_http_auth':
                    parsed_url = urlparse(base_url)
                    if parsed_url.username and parsed_url.password:
                        http_username = parsed_url.username
                        http_password = parsed_url.password
                        # Reconstruct URL without embedded credentials, preserving port if present
                        base_url = urlunparse(parsed_url._replace(netloc=parsed_url.hostname + (f":{parsed_url.port}" if parsed_url.port else "")))

                # Store resolved base_url and extracted HTTP auth credentials back into config_data
                config_data['base_url'] = base_url
                config_data['http_username'] = http_username
                config_data['http_password'] = http_password

                # Resolve username and password from environment variables if specified
                if config_data.get("username_env"):
                    config_data["username"] = os.getenv(config_data["username_env"])
                if config_data.get("password_env"):
                    config_data["password"] = os.getenv(config_data["password_env"])

                # Instantiate the server configuration dataclass with all resolved values
                config = SupersetServerConfig(**config_data)

                # Resolve relative cookie file path to absolute path
                if config.cookie_file_path and not os.path.isabs(config.cookie_file_path):
                    config.cookie_file_path = os.path.join(self._config_dir, config.cookie_file_path)

                # Create async HTTP client configured with the server's base URL
                client = httpx.AsyncClient(base_url=config.base_url, timeout=60.0, follow_redirects=True)
                token_path = self.get_token_path(server_id)
                # Store the context in the internal dictionary keyed by server_id
                self._contexts[server_id] = SupersetContext(
                    config=config,
                    client=client,
                    server_id=server_id,
                    token_path=token_path
                )
        except Exception as e:
            # Log any unexpected errors during server loading (malformed JSON, etc.)
            logger.error(f"Error loading servers: {e}")

    def get_context(self, server_id: str) -> Optional[SupersetContext]:
        """Retrieve the runtime context for a specific server by its ID.

        Automatically triggers load_servers() if no contexts have been loaded yet,
        ensuring lazy initialization of connections.

        Args:
            server_id: Unique identifier of the Superset server to look up.

        Returns:
            SupersetContext if the server is configured and loaded,
            None if the server_id does not exist or no contexts are available.
        """
        # Lazy-load servers on first request if not already loaded
        if not self._contexts:
            self.load_servers()
        return self._contexts.get(server_id)

    async def close_all(self):
        """Close all active HTTP client connections for every loaded server.

        Iterates over all cached contexts and calls aclose() on each httpx.AsyncClient
        to properly release network resources. Should be called during application shutdown.
        """
        for ctx in self._contexts.values():
            await ctx.client.aclose()
