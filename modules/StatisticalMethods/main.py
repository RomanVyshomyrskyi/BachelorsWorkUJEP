import os
import sys
import logging
from fastmcp import FastMCP
from typing import Optional, List, Union

def register(mcp: FastMCP):
    """Registers the Statistical Methods module."""

    @mcp.tool(name="test", description="rest registration")
    def test():
        return "Statistical Methods module registered successfully!"