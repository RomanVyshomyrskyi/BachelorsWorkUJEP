"""
Export/Import tool registration helpers.

Contains the tool registration functions for Superset export/import operations:
- export_superset_config: Export all resources from a server to JSON
- import_superset_config: Import resources from JSON into a target server
"""

import json
from typing import Optional, Dict
from fastmcp import FastMCP

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.export_import.export import export_superset_config as _export_config
from modules.SupersetModule.tools.export_import.import_ops import import_superset_config as _import_config


def register_export_import_tools(mcp: FastMCP, manager: ConnectionManager) -> None:
    """Register all export/import tools with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with.
        manager: The initialized ConnectionManager instance.
    """

    @mcp.tool(name="export_superset_config")
    async def tool_export_config(
        server_id: str,
        include_dashboards: bool = True,
        include_charts: bool = True,
        include_datasets: bool = True,
        include_databases: bool = True,
        include_css_templates: bool = True,
        include_annotations: bool = True,
    ) -> str:
        """Export all Superset resources (dashboards, charts, datasets, databases, CSS templates, annotations) to a single JSON structure for backup or migration."""
        return await _export_config(
            manager,
            server_id,
            include_dashboards=include_dashboards,
            include_charts=include_charts,
            include_datasets=include_datasets,
            include_databases=include_databases,
            include_css_templates=include_css_templates,
            include_annotations=include_annotations,
        )

    @mcp.tool(name="import_superset_config")
    async def tool_import_config(
        server_id: str,
        config_json: str,
        db_mappings: Optional[str] = None,
        create_missing_databases: bool = False,
        skip_existing: bool = True,
    ) -> str:
        """Import all Superset resources from exported JSON into a target server. Follows dependency order: databases -> datasets -> charts -> dashboards with automatic ID remapping."""
        db_map = None
        if db_mappings:
            try:
                db_map = json.loads(db_mappings)
            except json.JSONDecodeError:
                return json.dumps({
                    "error": "Invalid db_mappings JSON. Expected format: {\"source_db_id\": \"target_db_id\"}",
                    "received": db_mappings
                })

        return await _import_config(
            manager,
            server_id,
            config_json,
            db_mappings=db_map,
            create_missing_databases=create_missing_databases,
            skip_existing=skip_existing,
        )
