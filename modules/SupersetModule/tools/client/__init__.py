"""Client tools package for Superset MCP integration.

Re-exports key authentication and request functions for backward compatibility.
"""

from modules.SupersetModule.tools.client.auth import authenticate, ensure_auth
from modules.SupersetModule.tools.client.request import execute_request

__all__ = ["authenticate", "ensure_auth", "execute_request"]
