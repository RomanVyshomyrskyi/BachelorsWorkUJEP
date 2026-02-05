from fastmcp import FastMCP
from .tools.analysis import register_analysis_tools
from .tools.data import register_data_tools
from .tools.visualization import register_visualization_tools

def register(mcp: FastMCP):
    """
    Registers all tools for the DBAnalysis module.
    """
    register_analysis_tools(mcp)
    register_data_tools(mcp)
    register_visualization_tools(mcp)
