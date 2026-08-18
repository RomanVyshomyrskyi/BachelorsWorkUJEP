"""
Database Manager - Configuration loading and management for DBAnalysis.

Provides the DbManager class which loads database connection configurations
from a JSON file, resolves environment variable references for passwords,
and serves as the central configuration provider for the database strategy system.
"""

import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DbManager:
    """
    Manages database connection configurations loaded from a JSON file.

    This class reads database configurations (host, port, user, password, etc.)
    from a JSON file, validates required fields, resolves password environment
    variables, and provides access to individual database configs by ID.
        Configuration is stored in a JSON file (default: databases.json) with
        the structure: {"db_id": {"db_type": "...", "host": "...", ...}}.
        Each database config must have db_type, host, dbname, and user fields.
        Passwords can be specified directly or via a password_env reference
        that points to an environment variable name.

    Attributes:
        _configs: Dictionary mapping database IDs to their connection config dicts.
        _config_dir: Path to the directory containing the databases.json config file.

    Examples:
        >>> import tempfile, json, os
        >>> os.environ["DB_PASS"] = "s3cret"
        >>> # Create a test config file
        >>> d = tempfile.mkdtemp()
        >>> with open(f"{d}/databases.json", "w") as f:
        ...     json.dump({"mydb": {"db_type": "postgres", "host": "db.example.com",
        ...         "dbname": "analytics", "user": "admin",
        ...         "password_env": "DB_PASS"}}, f)
        >>> mgr = DbManager(d)
        >>> mgr.load_databases()
        >>> cfg = mgr.get_config("mydb")
        >>> cfg["host"]
        'db.example.com'
        >>> cfg["password"]
        's3cret'
        >>> mgr.get_config("nonexistent") is None
        True
    """

    def __init__(self, config_dir: str):
        """
        Initialize the DbManager with the directory containing database configs.

        Args:
            config_dir: Absolute or relative path to the directory containing
                        the databases.json configuration file.
            Sets up empty configuration storage and stores the path to the
            config directory for later file resolution.
        """
        # Dictionary to hold loaded database configurations keyed by db_id
        self._configs: Dict[str, dict] = {}
        # Directory where the databases.json config file lives
        self._config_dir = config_dir

    def load_databases(self, config_filename: str = "databases.json"):
        """
        Load database connection configurations from a JSON file.

        This method reads the databases.json file, validates each database
        entry for required fields (db_type, host, dbname, user), resolves
        password environment variable references, and stores valid configs
        in the internal _configs dictionary.

        Args:
            config_filename: Name of the JSON configuration file to load
                             (default: "databases.json").
            1. Constructs the full path to the config file.
            2. Returns early if the file does not exist (with a warning).
            3. Parses the JSON file into a dictionary.
            4. For each database entry:
               a. Validates required fields: db_type, host, dbname, user.
               b. Resolves password from password_env environment variable if present,
                  with fallback to direct password field.
               c. Resolves port from config or uses default for the db_type.
               d. Stores the validated config in _configs.
            5. Catches and logs any parsing or file access errors.

        Logs:
            info: For each successfully loaded database configuration.
            warning: When fields are missing or env vars are not set.
            error: When the entire file fails to load.
        """
        # Build the full path to the configuration file
        config_path = os.path.join(self._config_dir, config_filename)
        logger.info(f"Loading database config from {config_path}")

        # Return early if the configuration file doesn't exist
        if not os.path.exists(config_path):
            logger.warning(f"Config file {config_path} not found.")
            return

        try:
            # Parse the JSON configuration file into a dictionary
            with open(config_path, 'r') as f:
                db_configs = json.load(f)

            # Iterate over each database entry and validate/normalize its fields
            for db_id, config_data in db_configs.items():
                # Validate that db_type is specified
                db_type = config_data.get("db_type")
                if not db_type:
                    logger.warning(f"Database '{db_id}' missing db_type. Skipping.")
                    continue

                # Validate that host is specified
                host = config_data.get("host")
                if not host:
                    logger.warning(f"Database '{db_id}' missing host. Skipping.")
                    continue

                # Validate that dbname is specified
                dbname = config_data.get("dbname")
                if not dbname:
                    logger.warning(f"Database '{db_id}' missing dbname. Skipping.")
                    continue

                # Validate that user is specified
                user = config_data.get("user")
                if not user:
                    logger.warning(f"Database '{db_id}' missing user. Skipping.")
                    continue

                # Handle password: resolve from environment variable if password_env is set,
                # otherwise use the direct password field or set empty as fallback
                password = config_data.get("password")
                password_env = config_data.get("password_env")
                if password_env:
                    # Look up the environment variable and use its value if present
                    env_password = os.getenv(password_env)
                    if env_password:
                        password = env_password
                    # If env var is missing and no direct password exists, log warning
                    elif password is None:
                        logger.warning(
                            f"Database '{db_id}': password_env '{password_env}' is not set "
                            "and no fallback password is configured"
                        )
                # If password is still None after all resolution attempts, set to empty
                if password is None:
                    logger.warning(f"Database '{db_id}': No password configured")
                    password = ""

                # Resolve port: use config value or fall back to default for the db_type
                port = config_data.get("port") or _default_port(db_type)

                # Store the validated and normalized configuration
                self._configs[db_id] = {
                    "db_type": db_type,
                    "host": host,
                    "port": port,
                    "dbname": dbname,
                    "user": user,
                    "password": password,
                }
                # Log the successfully loaded configuration for debugging
                logger.info(f"Loaded database config: {db_id} ({db_type}://{host}:{port}/{dbname})")
        except Exception as e:
            # Log any errors during the entire loading process
            logger.error(f"Error loading databases: {e}")

    def get_config(self, db_id: str) -> Optional[dict]:
        """
        Retrieve the connection configuration for a specific database by ID.

        If no configurations have been loaded yet, this method triggers
        a lazy load of the databases.json file before attempting retrieval.

        Args:
            db_id: The unique identifier for the database configuration.

        Returns:
            A dictionary containing the database connection details (db_type,
            host, port, dbname, user, password) if found, or None if the
            database ID does not exist in the configuration.
            1. Checks if configs are loaded; if not, triggers lazy loading.
            2. Looks up the db_id in the internal _configs dictionary.
            3. Returns the config dict or None if not found.
        """
        # Lazy load configurations if they haven't been loaded yet
        if not self._configs:
            self.load_databases()
        return self._configs.get(db_id)


def _default_port(db_type: str) -> int:
    """
    Return the default port for a given database type.

    This is a fallback function used when a port is not explicitly
    specified in the database configuration.

    Args:
        db_type: The database type string (e.g., "postgres", "mariadb", "mysql", "mssql").

    Returns:
        The default port number as an integer. PostgreSQL defaults to 5432,
        MariaDB/MySQL to 3306, MSSQL to 1433. Unknown types default to 5432.
    """
    # Map known database types to their standard ports, defaulting to PostgreSQL port
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)
