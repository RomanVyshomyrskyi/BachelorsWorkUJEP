import os
import json
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class DbManager:
    def __init__(self, config_dir: str):
        self._configs: Dict[str, dict] = {}
        self._config_dir = config_dir

    def load_databases(self, config_filename: str = "databases.json"):
        config_path = os.path.join(self._config_dir, config_filename)
        logger.info(f"Loading database config from {config_path}")

        if not os.path.exists(config_path):
            logger.warning(f"Config file {config_path} not found.")
            return

        try:
            with open(config_path, 'r') as f:
                db_configs = json.load(f)

            for db_id, config_data in db_configs.items():
                db_type = config_data.get("db_type")
                if not db_type:
                    logger.warning(f"Database '{db_id}' missing db_type. Skipping.")
                    continue

                host = config_data.get("host")
                if not host:
                    logger.warning(f"Database '{db_id}' missing host. Skipping.")
                    continue

                dbname = config_data.get("dbname")
                if not dbname:
                    logger.warning(f"Database '{db_id}' missing dbname. Skipping.")
                    continue

                user = config_data.get("user")
                if not user:
                    logger.warning(f"Database '{db_id}' missing user. Skipping.")
                    continue

                password = config_data.get("password")
                password_env = config_data.get("password_env")
                if password_env:
                    env_password = os.getenv(password_env)
                    if env_password:
                        password = env_password
                    elif password is None:
                        logger.warning(
                            f"Database '{db_id}': password_env '{password_env}' is not set "
                            "and no fallback password is configured"
                        )
                if password is None:
                    logger.warning(f"Database '{db_id}': No password configured")
                    password = ""

                port = config_data.get("port") or _default_port(db_type)

                self._configs[db_id] = {
                    "db_type": db_type,
                    "host": host,
                    "port": port,
                    "dbname": dbname,
                    "user": user,
                    "password": password,
                }
                logger.info(f"Loaded database config: {db_id} ({db_type}://{host}:{port}/{dbname})")
        except Exception as e:
            logger.error(f"Error loading databases: {e}")

    def get_config(self, db_id: str) -> Optional[dict]:
        if not self._configs:
            self.load_databases()
        return self._configs.get(db_id)


def _default_port(db_type: str) -> int:
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)
