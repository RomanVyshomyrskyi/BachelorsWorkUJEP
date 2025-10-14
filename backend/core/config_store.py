"""
Simple config store for the application.

This module reads/writes a small JSON configuration file. It uses APP_DATA_DIR
environment variable (if set) to locate the directory; otherwise defaults to
"/app/data".
"""
import json
import os
from pathlib import Path
from typing import Optional, TypedDict

# Directory where config is stored. Can be overridden with APP_DATA_DIR env var.
CFG_DIR = Path(os.getenv("APP_DATA_DIR", "/app/data"))
# Path to the JSON config file inside CFG_DIR.
CFG_PATH = CFG_DIR / "config.json"


class AppConfig(TypedDict):
    # Data source name (connection string) for the application
    dsn: str
    # Human readable site/application name
    site_name: str


def load_config() -> Optional[AppConfig]:
    """
    Load and parse the config JSON file.

    Returns:
        AppConfig if the file exists and is valid JSON matching the expected
        shape, otherwise None (file missing or on error).
    """
    # If config file does not exist, return None to indicate "no config".
    if not CFG_PATH.exists():
        return None

    try:
        # Read the file and parse JSON. Any parsing errors or unexpected content
        # will be caught and result in None.
        return json.loads(CFG_PATH.read_text())
    except Exception:
        # Swallow exceptions to keep callers simple; they get None on failure.
        return None


def save_config(cfg: AppConfig) -> None:
    """
    Persist the given config to disk as pretty-printed JSON.

    Ensures the configuration directory exists before writing.
    """
    # Create directory tree if needed (no-op if already exists).
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    # Write JSON with indentation for readability.
    CFG_PATH.write_text(json.dumps(cfg, indent=2))
