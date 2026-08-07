"""Dashboard transfer between Superset servers.

Provides functionality to copy a dashboard and its linked charts from
one Superset server to another, with optional database and table mappings.
"""
from typing import Optional

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.transfer import transfer_dashboard as new_transfer_dashboard


async def transfer_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int,
    db_mappings: Optional[str] = None,
    table_mappings: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_transfer_dashboard - Transfer a dashboard between servers.

    Copies a dashboard and all its linked charts from one Superset server to
    another. Optionally maps database IDs and table names between the source
    and target servers for cross-environment transfers.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        source_server_id: The ID of the source Superset server.
        target_server_id: The ID of the target Superset server.
        dashboard_id: The numeric ID of the dashboard to transfer.
        db_mappings: Optional JSON string of database ID mappings between servers.
        table_mappings: Optional JSON string of table name mappings between servers.

    Returns:
        JSON string with transfer results, including updated chart/dashboard IDs
            on the target server. Returns NEED_INPUT if manual mappings are required.

    Example:
        result = await transfer_dashboard(
            manager, source_server_id="source", target_server_id="target",
            dashboard_id=789, db_mappings='{"1": 2}', table_mappings='{"old": "new"}'
        )
        # Returns JSON with transfer results including updated chart/dashboard IDs.
    """
    return await new_transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)
