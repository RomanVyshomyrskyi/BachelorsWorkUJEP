# SupersetMCP/main_SupersetMCP.py
import modelcontextprotocol as mcp
import logging
import asyncio
from typing import Any, Dict
import json # for placeholder tools

#
# This line is critical.
# It imports the 'tools.py' file from THIS folder,
# not the DataAnalysesMCP folder.
#
from . import tools

logger = logging.getLogger(__name__)

def main(config: Dict[str, Any]) -> None:
    """
    This is the main entry point for the "ASMCP" strategy.
    It reads the config and starts the MCP server.
    """
    logger.info("--- Starting Superset MCP (ASMCP) ---")

    # Get server settings from the config.json
    server_config = config.get("superset_server", {})
    host = server_config.get("host", "127.0.0.1")
    port = server_config.get("port", 8001) # Note: Different port!

    # This proves that only the Superset tools are loaded
    loaded_tools = [tool.__name__ for tool in mcp.get_tools()]
    logger.info(f"Loaded ASMCP tools: {loaded_tools}")

    logger.info(f"Starting ASMCP server at http://{host}:{port}")

    try:
        # This starts the server
        asyncio.run(mcp.serve(host=host, port=port))

    except KeyboardInterrupt:
        logger.info("ASMCP server shut down.")
    except Exception as e:
        logger.error(f"ASMCP server failed to start: {e}", exc_info=True)

    logger.info("--- Superset MCP (ASMCP) Finished ---")