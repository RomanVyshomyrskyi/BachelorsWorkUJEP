# main_loader.py
import importlib
import json
import logging
import sys
from pathlib import Path
from typing import Any, Callable, Dict

# --- Configuration ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# This maps the 'type' from config.json to the Python module
# that contains the 'main(config)' function.
MCP_MAPPINGS: Dict[str, str] = {
    "ASMCP": "SupersetMCP.main_SupersetMCP",
    "DAMCP": "DataAnalysesMCP.main_DataAnalyses",
    # Add new MCPs here
}
# --- End Configuration ---


def load_config(path: Path) -> Dict[str, Any]:
    """Loads the configuration file from the given path."""
    if not path.exists():
        logger.error("Config file not found: %s", path)
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_config_path(config_path_arg: str | None) -> Path:
    """Finds the config file path."""
    if config_path_arg:
        return Path(config_path_arg)

    cwd_path = Path.cwd() / "config.json"
    if cwd_path.exists():
        return cwd_path

    script_dir_path = Path(__file__).resolve().parent / "config.json"
    if script_dir_path.exists():
        return script_dir_path

    raise FileNotFoundError("Could not find 'config.json'.")


def main(config_path: str | None = None) -> None:
    """
    Main entry point.
    Loads config, finds the correct MCP, and executes its main function.
    """
    try:
        # 1. Find and load the configuration
        cfg_path_arg = config_path or (sys.argv[1] if len(sys.argv) > 1 else None)
        cfg_path = find_config_path(cfg_path_arg)
        config = load_config(cfg_path)

        # 2. Get the strategy type from the config
        strategy_type = config.get("type")
        if not strategy_type:
            raise KeyError("Config must contain a 'type' field indicating the strategy.")

        # 3. Find the module to run from our mapping
        module_name = MCP_MAPPINGS.get(strategy_type)
        if not module_name:
            raise ValueError(
                f"Unknown strategy type: {strategy_type}. "
                f"Available types: {list(MCP_MAPPINGS.keys())}"
            )

        logger.info("Using MCP type '%s' from config %s", strategy_type, cfg_path)
        logger.info("Loading module: %s", module_name)

        # 4. Dynamically import *only* the module we need
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            logger.error(
                "Failed to import module '%s'. Error: %s",
                module_name, e
            )
            sys.exit(1)

        # 5. Find the 'main' function within that module
        main_fn = getattr(module, "main", None)
        if not callable(main_fn):
            raise AttributeError(
                f"Module {module_name} does not have a "
                "callable 'main(config)' function."
            )

        # 6. Run the selected MCP's main function
        main_fn(config)

    except Exception as e:
        logger.error("A critical error occurred: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()