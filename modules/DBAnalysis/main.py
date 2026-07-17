import os
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry
from .tools.analysis import register_analysis_tools
from .tools.data import register_data_tools
from .tools.visualization import register_visualization_tools
from .strategies.factory import get_db_strategy
from .utils.rules_loader import get_normalization_rules
from .db_manager import DbManager

depends_on = []

def get_module_api():
    return {
        "get_db_strategy": get_db_strategy,
        "get_normalization_rules": get_normalization_rules,
    }

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    module_dir = os.path.dirname(__file__)
    db_manager = DbManager(module_dir)
    db_manager.load_databases()

    register_analysis_tools(mcp, db_manager)
    register_data_tools(mcp, db_manager)
    register_visualization_tools(mcp, db_manager)

    if registry is not None:
        registry.register_module_api("DBAnalysis", get_module_api())
