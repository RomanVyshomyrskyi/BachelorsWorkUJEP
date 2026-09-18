"""
DBAnalysis Module - MCP Tools for Database Analysis.

This module provides FastMCP tools for analyzing database schemas,
executing read-only SQL queries, and generating visualizations across
PostgreSQL, MariaDB/MySQL, and Microsoft SQL Server databases.

The module follows a strategy pattern where each database type has its
own implementation for connection, schema extraction, and query execution,
all enforcing read-only access to prevent data modification.
"""

import os
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry
from .tools.analysis import register_analysis_tools
from .tools.data import register_data_tools
from .tools.visualization import register_visualization_tools
from .tools.dml import register_dml_tools
from .tools.data_import import register_import_tools
from .strategies.factory import get_db_strategy
from .utils.rules_loader import get_normalization_rules
from .db_manager import DbManager

depends_on = []


def get_module_api():
    """
    Return the public API dictionary for the DBAnalysis module.

    This function exposes the core utility functions that other modules
    or consumers can import directly without going through the MCP tool
    registration system.
        Maps function names to their implementations for external use
        by dependent modules or the application registry.

    Returns:
        dict: A dictionary mapping function names to callables, including
              'get_db_strategy' for database strategy instantiation and
              'get_normalization_rules' for loading normalization rules.
    """
    return {
        "get_db_strategy": get_db_strategy,
        "get_normalization_rules": get_normalization_rules,
    }


def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    """
    Register all DBAnalysis MCP tools and optionally expose the module API.

    This function initializes the database manager, loads database
    configurations from the JSON config file, and registers all MCP
    tools for analysis, data access, and visualization.

    Args:
        mcp: The FastMCP server instance to register tools on.
        registry: Optional ModuleRegistry for exposing the module API
                  to other parts of the application.
        1. Creates a DbManager instance using the module's directory
           as the configuration directory.
        2. Loads database configurations from databases.json.
        3. Registers analysis, data, and visualization tools with the MCP server.
        4. If a registry is provided, exposes the module API for external use.
    """
    # Determine the directory where this module lives for config file resolution
    module_dir = os.path.dirname(__file__)

    # Initialize the database manager and load available database configs
    db_manager = DbManager(module_dir)
    db_manager.load_databases()

    # Register all MCP tool categories with the FastMCP server
    register_analysis_tools(mcp, db_manager)
    register_data_tools(mcp, db_manager)
    register_visualization_tools(mcp, db_manager)
    register_dml_tools(mcp, db_manager)
    register_import_tools(mcp, db_manager)

    # Expose core module functions via the registry if provided
    if registry is not None:
        registry.register_module_api("DBAnalysis", get_module_api())
