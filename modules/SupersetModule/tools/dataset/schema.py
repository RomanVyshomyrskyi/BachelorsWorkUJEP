"""
Dataset schema definitions for Apache Superset MCP.

Re-exports schema types used across the dataset module.
"""

try:
    from modules.SupersetModule.schemas.dataset import DatabaseSchemaResponse
except ImportError:
    DatabaseSchemaResponse = None

__all__ = ["DatabaseSchemaResponse"] if DatabaseSchemaResponse else []
