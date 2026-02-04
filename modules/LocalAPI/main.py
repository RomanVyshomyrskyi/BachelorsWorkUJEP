import os
import socket
from fastmcp import FastMCP

def register(mcp: FastMCP):
    """
    Registers Local API helper tools.
    """

    @mcp.tool(name="get_local_api_info")
    def get_api_info() -> str:
        """
        Returns information about the running Local API (if available).
        """
        # Check if we are likely running in SSE mode (usually on port 8000 or similar)
        # This is a heuristic since we might not know the exact port if dynamically assigned
        
        # We can try to guess or just return general info
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
