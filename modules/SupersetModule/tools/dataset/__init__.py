"""
Dataset management tools for Apache Superset MCP integration.

Provides tools for listing, creating, and inspecting datasets (both physical
tables and virtual datasets with custom SQL). Also includes database schema
extraction for understanding table structures across different database engines.

MCP Tools Provided:
    - superset_list_datasets: List all datasets on a Superset server
    - superset_get_dataset_info: Get details for a specific dataset
    - superset_create_virtual_dataset: Create a virtual dataset from SQL
    - superset_create_dataset: Create a dataset from a physical table
    - superset_get_database_schema: Extract schema (tables/columns) from a database
"""

# Re-export all public functions for backward compatibility
from modules.SupersetModule.tools.dataset.create import create_dataset
from modules.SupersetModule.tools.dataset.create_virtual import create_virtual_dataset
from modules.SupersetModule.tools.dataset.info import list_datasets, get_dataset_info, get_database_schema

__all__ = [
    "create_dataset",
    "create_virtual_dataset",
    "list_datasets",
    "get_dataset_info",
    "get_database_schema",
]
