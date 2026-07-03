import os
import socket
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

depends_on = []

def get_module_api():
    return {}

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    @mcp.tool(name="get_local_api_info")
    def get_api_info() -> str:
        hostname = socket.gethostname()
        local_ip = socket.gethostbyname(hostname)

        return f"""
Local API Info:
Hostname: {hostname}
IP: {local_ip}

To use with Open Web UI:
1. Ensure the server is running in SSE mode (python main.py --sse).
2. The URL is typically http://localhost:8000/sse
3. Configure Open Web UI to point to this URL as an OpenAI-compatible endpoint or MCP server.
"""

    if registry is not None:
        registry.register_module_api("LocalAPI", get_module_api())
