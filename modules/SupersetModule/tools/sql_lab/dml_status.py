"""
DML status check for Superset databases.

Provides tools to check if a Superset database has DML operations enabled
by inspecting the 'extra' JSON field of the database configuration.
Detects multiple possible setting names automatically.
"""

import json
import time
from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import DatabaseError
from modules.metrics import get_metrics

# Possible DML setting names in Superset database extra JSON
DML_SETTING_NAMES = [
    'allow_dml',
    'allow_run_dml',
    'allow_sql_lab_ddl',
    'allow_ddl',
    'allow_insert',
    'allow_update',
    'allow_delete',
]


async def check_database_dml_status(
    manager: ConnectionManager,
    server_id: str,
    database_id: int
) -> str:
    """
    MCP Tool: superset_check_database_dml_status - Check if a Superset database allows DML.

    Fetches database configuration from Superset and inspects the 'extra' JSON field
    to detect if DML operations (INSERT, UPDATE, DELETE) are enabled. Checks multiple
    possible setting names automatically.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to inspect.

    Returns:
        JSON string containing:
        - database_name: Name of the database
        - engine_name: Database engine type (postgres, mysql, etc.)
        - dml_allowed: Whether DML is enabled
        - setting_found: Which setting key was found (if any)
        - extra: Full extra field contents for reference
        - checked_settings: List of setting names that were checked
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return DatabaseError(f"Server '{server_id}' not found.", status_code=404).to_json()

    start_time = time.monotonic()
    try:
        api_response = await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/database/{database_id}"
        )

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_check_database_dml", status="success").inc()
        mc.tool_duration.labels(tool="superset_check_database_dml").observe(
            time.monotonic() - start_time
        )

        try:
            response_data = json.loads(api_response)
        except json.JSONDecodeError:
            return DatabaseError(
                f"Failed to parse database info response for database_id={database_id}"
            ).to_json()

        database_name = response_data.get('database_name', 'Unknown')
        engine_name = response_data.get('engine_name', 'Unknown')
        extra = response_data.get('extra', {})

        if isinstance(extra, str):
            try:
                extra = json.loads(extra)
            except (json.JSONDecodeError, TypeError):
                extra = {}

        dml_allowed = False
        setting_found = None

        for setting_name in DML_SETTING_NAMES:
            if setting_name in extra:
                value = extra[setting_name]
                if isinstance(value, bool):
                    dml_allowed = value
                elif isinstance(value, str):
                    dml_allowed = value.lower() in ('true', '1', 'yes', 'enabled')
                elif isinstance(value, (int, float)):
                    dml_allowed = value > 0
                setting_found = setting_name
                break

        result = {
            "database_name": database_name,
            "engine_name": engine_name,
            "dml_allowed": dml_allowed,
            "setting_found": setting_found,
            "extra": extra,
            "checked_settings": DML_SETTING_NAMES,
        }

        return json.dumps(result, indent=2)

    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_check_database_dml", status="error").inc()
        mc.record_error(tool="superset_check_database_dml", error_message=str(e))
        return DatabaseError(
            f"Error checking DML status for database_id={database_id}: {e}"
        ).to_json()
