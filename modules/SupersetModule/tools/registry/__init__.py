"""
Registry module for Superset MCP tool registration.

This module provides the main register() function that sets up all Superset
tools and the connection manager. Tools are organized into grouped submodules
for maintainability.

Usage:
    from modules.SupersetModule.tools.registry import register, get_module_api
    register(mcp_instance, registry_instance)
"""
from modules.SupersetModule.tools.registry.register import get_module_api, register

# Re-export for backward compatibility
register_superset_module = register

__all__ = [
    "register",
    "register_superset_module",
    "get_module_api",
]
