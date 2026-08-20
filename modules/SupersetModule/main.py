"""Superset MCP Module entry point and FastMCP tool registration.

This module serves as the main entry point for the SupersetModule within the
MCP (Model Context Protocol) framework. It:
- Initializes the ConnectionManager with the module's directory
- Loads all server configurations on module registration
- Registers 50+ MCP tools covering server management, resource CRUD operations,
  chart/dashboard creation, SQL Lab execution, database profiling, and transfer operations
- Exposes module API internals for inter-module communication via the registry

Tools are organized into logical groups (server, resources, charts, dashboards,
datasets, databases, sqllab, transfer, explore, system, semantic) imported
from the tools subpackage and wrapped with @mcp.tool decorators.
"""
import os
import sys
import logging
from typing import Optional, List, Union
from fastapi import Query
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools import server
from modules.SupersetModule.tools import general
from modules.SupersetModule.tools import resources
from modules.SupersetModule.tools import charts
from modules.SupersetModule.tools import dashboards
from modules.SupersetModule.tools import datasets
from modules.SupersetModule.tools import databases
from modules.SupersetModule.tools import sqllab
from modules.SupersetModule.tools import transfer
from modules.SupersetModule.tools import explore
from modules.SupersetModule.tools import system
from modules.SupersetModule.tools import semantic

# Configure structured logging with timestamp, module name, and log level
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

# This module has no dependencies on other modules
depends_on = []


def get_module_api():
    """Return a dictionary of internal APIs for inter-module communication.

    Provides programmatic access to core SupersetModule functionality that other
    modules may need, including the ConnectionManager class and key request helpers.

    Returns:
        Dictionary mapping API names to their callable implementations:
        - "ConnectionManager": The ConnectionManager class for creating new contexts
        - "api_request": The superset API request handler function
        - "execute_request": The authenticated HTTP request executor with token refresh
    """
    return {
        "ConnectionManager": ConnectionManager,
        "api_request": general.impl_superset_api,
        "execute_request": __import__("modules.SupersetModule.api_client", fromlist=["execute_request"]).execute_request,
    }


def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    """Register all Superset MCP tools and initialize the connection manager.

    This is the main entry point called by the MCP server during startup. It
    creates a ConnectionManager, loads server configurations, and registers
    all tool handlers with the FastMCP instance.

    Args:
        mcp: The FastMCP instance to register tools with. Tools are bound
            to this instance and become available to the LLM.
        registry: Optional ModuleRegistry for inter-module API exposure.
            If provided, the module's internal API dictionary is registered
            under the key "SupersetModule".
    """
    # Resolve the module's directory path for config file resolution
    module_dir = os.path.dirname(__file__)
    # Create and initialize the connection manager with server configurations
    manager = ConnectionManager(module_dir)
    manager.load_servers()

    # --- Server Management Tools ---

    @mcp.tool(name="list_superset_servers")
    async def tool_list_servers() -> str:
        """Lists all configured Superset servers."""
        return await server.list_servers(manager)

    @mcp.tool(name="superset_reauthenticate")
    async def tool_reauthenticate(server_id: str) -> str:
        """Forces re-authentication with a Superset server."""
        return await server.reauthenticate(manager, server_id)

    @mcp.tool(name="superset_server_status")
    async def tool_server_status(server_id: str) -> str:
        """Checks the status and connectivity of a specific Superset server."""
        return await server.server_status(manager, server_id)

    # --- Resource Discovery Tools ---

    @mcp.tool(name="superset_available_resource_types")
    async def tool_list_resource_types() -> str:
        """Lists all available resource types for superset_list_resources."""
        return await resources.list_resource_types()

    # REMOVED: direct API access disabled for agent safety.
    # @mcp.tool(name="superset_api_request")
    # async def tool_superset_api(server_id: str, method: str, endpoint: str, json_body: Optional[str] = None, params: Optional[str] = None) -> str:
    #     """Executes a raw API request against a Superset server (GET/POST/PUT only, DELETE forbidden)."""
    #     return await general.superset_api_request(manager, server_id, method, endpoint, json_body, params)

    @mcp.tool(name="superset_list_resources")
    async def tool_list_resources(server_id: str, resource_type: str) -> str:
        """Lists resources of a specific type. Wrapper around GET /api/v1/{resource_type}/."""
        return await resources.list_resources(manager, server_id, resource_type)

    @mcp.tool(name="list_dashboards")
    async def tool_list_dashboards(server_id: str) -> str:
        """Lists dashboards on a specific server to get their IDs."""
        return await resources.list_dashboards(manager, server_id)

    @mcp.tool(name="superset_get_resource")
    async def tool_get_resource(server_id: str, resource_type: str, resource_id: Union[int, str]) -> str:
        """Gets details for a specific resource by ID. Wrapper around GET /api/v1/{resource_type}/{pk}."""
        return await resources.get_resource(manager, server_id, resource_type, resource_id)

    # --- Chart Tools ---

    @mcp.tool(name="superset_get_chart_api_info")
    async def tool_get_chart_api_info(server_id: str) -> str:
        """Retrieves metadata about the chart API from _info endpoint (filters, permissions, properties)."""
        return await charts.get_chart_api_info(manager, server_id)

    # REMOVED: superset_create_chart — consolidated into generate_chart (2025-07-22)
    # @mcp.tool(name="superset_create_chart")
    # async def tool_create_chart(server_id: str, slice_name: str, viz_type: str, datasource_id: int, datasource_type: str, params: str, description: Optional[str] = None) -> str:
    #     """Creates a new chart with auto-fix validation."""
    #     return await charts.create_chart(manager, server_id, slice_name, viz_type, datasource_id, datasource_type, params, description)

    @mcp.tool(name="superset_generate_simple_dashboard_layout")
    async def tool_generate_simple_dashboard_layout(server_id: str, chart_ids: List[int] = None, layout_type: str = "row_of_charts", chart_width: int = 6, chart_height: int = 50, body: Optional[dict] = None) -> str:
        """Generates a valid position_json arranging charts in a simple row/column layout."""
        if chart_ids is None and body:
            val = body.get("chart_ids")
            if val:
                chart_ids = val if isinstance(val, list) else []
        if chart_ids is None:
            from modules.SupersetModule.exceptions import DashboardError
            from modules.log_utils import LogCollector
            log = LogCollector(__name__)
            return log.collect(DashboardError("chart_ids is required.").to_json())
        return await dashboards.generate_simple_dashboard_layout(manager, server_id, chart_ids, layout_type, chart_width, chart_height)

    @mcp.tool(name="superset_create_dashboard")
    async def tool_create_dashboard(server_id: str, dashboard_title: str, position_json: str, slug: Optional[str] = None, json_metadata: Optional[str] = None, owners: Optional[List[int]] = None, roles: Optional[List[int]] = None, published: Optional[bool] = False) -> str:
        """Creates a new dashboard on a Superset server."""
        return await dashboards.create_dashboard(manager, server_id, dashboard_title, position_json, slug, json_metadata, owners, roles, published)

    @mcp.tool(name="superset_create_dataset")
    async def tool_create_dataset(server_id: str, table_name: str, database_id: int, schema: Optional[str] = None, owners: Optional[List[int]] = None, metrics_json: Optional[str] = None, columns_json: Optional[str] = None, sql_expression: Optional[str] = None) -> str:
        """Creates a new dataset on a Superset server."""
        return await datasets.create_dataset(manager, server_id, table_name, database_id, schema, owners, metrics_json, columns_json, sql_expression)

    # --- SQL Lab Tools ---

    @mcp.tool(name="superset_sqllab_execute_query")
    async def tool_sqllab_execute_query(server_id: str, database_id: int, sql_query: str, schema: Optional[str] = None, client_id: Optional[str] = None, tab_name: Optional[str] = None) -> str:
        """Executes an SQL query through Superset's SQL Lab API."""
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema, client_id, tab_name)

    @mcp.tool(name="superset_sqllab_get_query_results")
    async def tool_sqllab_get_query_results(server_id: str, client_id: str) -> str:
        """Retrieves the results of a previously executed SQL Lab query."""
        return await sqllab.sqllab_get_query_results(manager, server_id, client_id)

    # --- Transfer Tools ---

    @mcp.tool(name="transfer_dashboard")
    async def tool_transfer_dashboard(source_server_id: str, target_server_id: str, dashboard_id: int, db_mappings: Optional[str] = None, table_mappings: Optional[str] = None) -> str:
        """Transfers a dashboard (and its charts) between servers. 3-phase: datasets→charts→dashboard. Returns NEED_INPUT if mappings required."""
        return await transfer.transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)

    @mcp.tool(name="superset_get_database_schema")
    async def tool_get_database_schema(server_id: str, database_id: int, schema_name: Optional[str] = None) -> str:
        """Retrieves schema (tables/columns) via information_schema SQL Lab queries."""
        return await datasets.get_database_schema(manager, server_id, database_id, schema_name)

    # --- Dashboard Tools ---

    @mcp.tool(name="superset_get_dashboard_api_info")
    async def tool_get_dashboard_api_info(server_id: str) -> str:
        """Retrieves metadata about the dashboard API from _info endpoint."""
        return await dashboards.get_dashboard_api_info(manager, server_id)

    @mcp.tool(name="superset_update_chart")
    async def tool_update_chart(server_id: str, chart_id: int, json_body: str) -> str:
        """Updates an existing chart. json_body contains fields to update."""
        return await charts.update_chart(manager, server_id, chart_id, json_body)

    @mcp.tool(name="superset_update_dashboard")
    async def tool_update_dashboard(server_id: str, dashboard_id: int, json_body: str) -> str:
        """Updates an existing dashboard. json_body contains fields to update."""
        return await dashboards.update_dashboard(manager, server_id, dashboard_id, json_body)

    @mcp.tool(name="superset_bulk_link_charts_to_dashboard")
    async def tool_bulk_link_charts(server_id: str, dashboard_id: int, chart_ids: List[int] = None, body: Optional[dict] = None) -> str:
        """Links multiple charts to a dashboard in bulk."""
        if chart_ids is None and body:
            val = body.get("chart_ids")
            if val:
                chart_ids = val if isinstance(val, list) else []
        if chart_ids is None:
            from modules.SupersetModule.exceptions import DashboardError
            from modules.log_utils import LogCollector
            log = LogCollector(__name__)
            return log.collect(DashboardError("chart_ids is required.").to_json())
        return await dashboards.bulk_link_charts(manager, server_id, dashboard_id, chart_ids)

    @mcp.tool(name="superset_generate_robust_dashboard_layout")
    async def tool_generate_robust_layout(server_id: str, chart_ids: List[int] = None, body: Optional[dict] = None) -> str:
        """Generates a nested position_json with ROOT→GRID→ROW→CHART hierarchy."""
        if chart_ids is None and body:
            val = body.get("chart_ids")
            if val:
                chart_ids = val if isinstance(val, list) else []
        if chart_ids is None:
            from modules.SupersetModule.exceptions import DashboardError
            from modules.log_utils import LogCollector
            log = LogCollector(__name__)
            return log.collect(DashboardError("chart_ids is required.").to_json())
        return await dashboards.generate_robust_layout(manager, server_id, chart_ids)

    # --- Chart Configuration Tools ---

    @mcp.tool(name="superset_get_standard_chart_params")
    def tool_get_standard_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
        """Returns standard chart params for a viz type to prevent empty query errors."""
        return charts.get_standard_chart_params(viz_type, datasource_id, overrides_json)

    @mcp.tool(name="superset_get_chart_creation_rules")
    def tool_get_chart_rules() -> str:
        """Returns expert rules for creating functional charts."""
        return charts.get_chart_creation_rules()

    @mcp.tool(name="superset_get_dashboard_creation_rules")
    def tool_get_dashboard_rules() -> str:
        """Returns expert rules for creating functional dashboards."""
        return dashboards.get_dashboard_creation_rules()

    # --- Chart Management Tools ---

    @mcp.tool(name="list_charts")
    async def tool_list_charts(server_id: str) -> str:
        """Lists all charts on a server. GET /api/v1/chart/."""
        return await charts.list_charts(manager, server_id)

    @mcp.tool(name="get_chart_info")
    async def tool_get_chart_info(server_id: str, chart_id: Union[int, str]) -> str:
        """Gets detailed information for a specific chart by ID."""
        return await charts.get_chart_info(manager, server_id, chart_id)

    # --- Database Management Tools ---

    @mcp.tool(name="list_databases")
    async def tool_list_databases(server_id: str) -> str:
        """Lists all database connections. GET /api/v1/database/."""
        return await databases.list_databases(manager, server_id)

    @mcp.tool(name="get_database_info")
    async def tool_get_database_info(server_id: str, database_id: int) -> str:
        """Gets detailed information for a specific database connection by ID."""
        return await databases.get_database_info(manager, server_id, database_id)

    # --- Dataset Management Tools ---

    @mcp.tool(name="list_datasets")
    async def tool_list_datasets(server_id: str) -> str:
        """Lists all datasets. GET /api/v1/dataset/."""
        return await datasets.list_datasets(manager, server_id)

    @mcp.tool(name="get_dataset_info")
    async def tool_get_dataset_info(server_id: str, dataset_id: Union[int, str]) -> str:
        """Gets detailed information for a specific dataset by ID."""
        return await datasets.get_dataset_info(manager, server_id, dataset_id)

    # --- Dashboard Info Tools ---

    @mcp.tool(name="get_dashboard_info")
    async def tool_get_dashboard_info(server_id: str, dashboard_id: Union[int, str]) -> str:
        """Gets detailed information for a specific dashboard by ID."""
        return await dashboards.get_dashboard_info(manager, server_id, dashboard_id)

    # --- Chart Creation & Data Tools ---

    @mcp.tool(name="generate_chart")
    async def tool_generate_chart(server_id: str, dataset_id: int, config: str, slice_name: Optional[str] = None, description: Optional[str] = None) -> str:
        """Create and save a new chart. Use generate_explore_link for ad-hoc exploration."""
        return await charts.generate_chart(manager, server_id, dataset_id, config, slice_name, description)

    @mcp.tool(name="get_chart_preview")
    async def tool_get_chart_preview(server_id: str, chart_id: Union[int, str]) -> str:
        """Get a visual preview URL for a chart."""
        return await charts.get_chart_preview(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_data")
    async def tool_get_chart_data(server_id: str, chart_id: Union[int, str]) -> str:
        """Get underlying chart data in text-friendly format."""
        return await charts.get_chart_data(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_type_schema")
    async def tool_get_chart_type_schema(server_id: str, chart_type: str) -> str:
        """Get schema for a specific chart type (expected params/config)."""
        return await charts.get_chart_type_schema(manager, server_id, chart_type)

    @mcp.tool(name="superset_get_all_chart_schemas")
    async def tool_get_all_chart_schemas(server_id: str) -> str:
        """Discover ALL chart types from Superset and return a consolidated Markdown reference. Use BEFORE generating charts to get the complete, up-to-date list of chart types with their required parameters. Cached for 24 hours."""
        return await charts.get_all_chart_schemas(manager, server_id)

    # --- Dashboard Creation Tools ---

    @mcp.tool(name="generate_dashboard")
    async def tool_generate_dashboard(
        server_id: str,
        dashboard_title: str,
        chart_ids: Optional[str] = None,
        slug: Optional[str] = None,
        json_metadata: Optional[str] = None,
        published: bool = False,
        layout_type: str = "robust",
        body: Optional[dict] = None
    ) -> str:
        """Create a new dashboard from chart IDs with auto-generated layout."""
        import json
        parsed_ids = []
        if chart_ids:
            stripped = chart_ids.strip()
            if stripped.startswith("["):
                try:
                    parsed_ids = json.loads(stripped)
                    if not isinstance(parsed_ids, list):
                        parsed_ids = []
                    else:
                        parsed_ids = [int(x) for x in parsed_ids]
                except (json.JSONDecodeError, ValueError, TypeError):
                    parsed_ids = []
            elif "," in stripped:
                try:
                    parsed_ids = [int(x.strip()) for x in stripped.split(",") if x.strip()]
                except ValueError:
                    parsed_ids = []
            else:
                try:
                    parsed_ids = [int(stripped)]
                except ValueError:
                    parsed_ids = []

        if not parsed_ids:
            if body:
                val = body.get("chart_ids")
                if val:
                    parsed_ids = val if isinstance(val, list) else []

        if not parsed_ids:
            from modules.SupersetModule.exceptions import DashboardError
            from modules.log_utils import LogCollector
            log = LogCollector(__name__)
            return log.collect(DashboardError("chart_ids is required.").to_json())
        return await dashboards.generate_dashboard(manager, server_id, dashboard_title, parsed_ids, slug, json_metadata, published, layout_type)

    @mcp.tool(name="add_chart_to_existing_dashboard")
    async def tool_add_chart_to_existing_dashboard(server_id: str, dashboard_id: int, chart_id: int) -> str:
        """Add a chart to an existing dashboard. Preferred over generate_dashboard for existing dashboards."""
        return await dashboards.add_chart_to_existing_dashboard(manager, server_id, dashboard_id, chart_id)

    # --- Virtual Dataset & Explore Tools ---

    @mcp.tool(name="create_virtual_dataset")
    async def tool_create_virtual_dataset(server_id: str, dataset_name: str, database_id: int, sql: str, schema: Optional[str] = None, description: Optional[str] = None) -> str:
        """Save a SQL query as a virtual dataset for charting."""
        return await datasets.create_virtual_dataset(manager, server_id, dataset_name, database_id, sql, schema, description)

    @mcp.tool(name="generate_explore_link")
    async def tool_generate_explore_link(server_id: str, dataset_id: int, config: Optional[str] = None) -> str:
        """Generate interactive explore URL. Does NOT create a permanent chart."""
        return await explore.generate_explore_link(manager, server_id, dataset_id, config)

    # --- Additional SQL Lab Tools ---

    @mcp.tool(name="execute_sql")
    async def tool_execute_sql(server_id: str, database_id: int, sql_query: str, schema: Optional[str] = None) -> str:
        """Execute SQL queries and get results."""
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema)

    @mcp.tool(name="save_sql_query")
    async def tool_save_sql_query(server_id: str, database_id: int, label: str, sql: str, schema: Optional[str] = None, description: Optional[str] = None) -> str:
        """Save a SQL query to Saved Queries list."""
        return await sqllab.save_sql_query(manager, server_id, database_id, label, sql, schema, description)

    @mcp.tool(name="open_sql_lab_with_context")
    async def tool_open_sql_lab_with_context(server_id: str, database_id: int, sql: Optional[str] = None, schema: Optional[str] = None) -> str:
        """Generate SQL Lab URL with pre-filled sql."""
        return await sqllab.open_sql_lab_with_context(manager, server_id, database_id, sql, schema)

    # --- System & Metadata Tools ---

    @mcp.tool(name="get_schema")
    async def tool_get_schema(server_id: str, model_type: Optional[str] = None) -> str:
        """Get schema metadata (filterable/sortable columns) for chart/dataset/dashboard/database."""
        return await system.get_schema(manager, server_id, model_type)

    @mcp.tool(name="get_instance_info")
    async def tool_get_instance_info(server_id: str) -> str:
        """Get instance info: user identity, feature flags, metadata."""
        return await system.get_instance_info(manager, server_id)

    @mcp.tool(name="health_check")
    async def tool_health_check(server_id: str) -> str:
        """Check the health status of a Superset server."""
        return await system.health_check(manager, server_id)

    # --- Export/Import Tools ---

    @mcp.tool(name="export_dashboard_to_json")
    async def tool_export_dashboard(server_id: str, dashboard_id: int) -> str:
        """Export ONE dashboard with ALL its charts (full params, viz_type, datasource refs), datasets (columns, metrics, SQL), databases (connection configs), and layout (position_json) into a single JSON file.

        Use this tool to create a portable backup of a dashboard that can be imported into another Superset instance with identical chart placement, parameters, and datasource references.

        Args:
            server_id: The Superset server ID (as defined in servers.json). E.g. "production", "dev", "staging".
            dashboard_id: The integer ID of the dashboard to export.

        Returns:
            JSON string containing the full export with metadata, dashboards, charts, datasets, databases, summary, and timing info.

        Example:
            # Export dashboard ID 42 from the production server
            result = await tool_export_dashboard(
                server_id="production",
                dashboard_id=42
            )
            # result is a JSON string you can save to a file:
            # with open("dashboard_42_export.json", "w") as f:
            #     f.write(result)
            # Then pass that JSON to import_dashboard_from_json on another server.
        """
        from modules.SupersetModule.tools.export_import import export_dashboard_to_json as _export_dash
        return await _export_dash(manager, server_id, dashboard_id)

    @mcp.tool(name="import_dashboard_from_json")
    async def tool_import_dashboard(config_json: str, target_server_id: str, db_mapping: Optional[str] = None, skip_existing: bool = True) -> str:
        """Import a dashboard export JSON into a target Superset server. Recreates the dashboard with all charts (full params preserved), datasets, and databases with automatic ID remapping.

        Follows strict dependency order: databases → datasets → charts → dashboard. All datasource references, chart IDs in position_json, and database references are remapped automatically.

        Args:
            config_json: The full JSON string from export_dashboard_to_json. Can be the raw JSON output or file contents.
            target_server_id: The Superset server ID to import into (e.g. "dev", "staging", "production").
            db_mapping: Optional JSON string mapping source database IDs to target database IDs. Format: {"1": 5, "2": 7}. Only needed when the target server has differently numbered databases. If omitted, databases are matched by name.
            skip_existing: If True (default), skip resources that already exist on the target (matched by name). Set to False to force recreation (may fail if names conflict).

        Returns:
            JSON string with the import report: summary counts, id_mappings (source→new), errors, and timing.

        Example:
            # Simple import: databases matched by name
            result = await tool_import_dashboard(
                config_json=open("dashboard_42_export.json").read(),
                target_server_id="dev"
            )

            # Import with explicit database mapping (source db 1 → target db 3)
            result = await tool_import_dashboard(
                config_json=open("dashboard_42_export.json").read(),
                target_server_id="staging",
                db_mapping='{"1": 3}',
                skip_existing=True
            )
        """
        import json
        db_map = None
        if db_mapping:
            try:
                db_map = json.loads(db_mapping)
            except json.JSONDecodeError:
                from modules.log_utils import LogCollector
                log = LogCollector(__name__)
                from modules.SupersetModule.exceptions import ChartError
                return log.collect(ChartError("Invalid db_mapping JSON. Expected format: {\"source_db_id\": \"target_db_id\"}").to_json())

        from modules.SupersetModule.tools.export_import import import_dashboard_from_json as _import_dash
        return await _import_dash(manager, target_server_id, config_json, db_mapping=db_map, skip_existing=skip_existing)

    # --- Semantic & Data Profiling Tools ---

    @mcp.tool(name="profile_table")
    async def tool_profile_table(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Profile a database table: row count, column stats, nulls, distinct, min/max/avg, stddev, top values."""
        return await semantic.profile_table(manager, server_id, database_id, schema, table)

    @mcp.tool(name="suggest_metrics")
    async def tool_suggest_metrics(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Auto-suggest aggregate metrics (SUM, AVG, COUNT, MIN, MAX) for numeric columns."""
        return await semantic.suggest_metrics(manager, server_id, database_id, schema, table)

    @mcp.tool(name="suggest_dimensions")
    async def tool_suggest_dimensions(server_id: str, database_id: int, schema: str, table: str) -> str:
        """Auto-suggest dimension columns (text/categorical/date/boolean) for grouping and filtering."""
        return await semantic.suggest_dimensions(manager, server_id, database_id, schema, table)

    @mcp.tool(name="get_data_dictionary")
    async def tool_get_data_dictionary(server_id: str, database_id: int, schema: str, table: str, include_statistics: bool = True) -> str:
        """Generate a data dictionary for a table: column names, types, categories, recommended roles, and optional statistics."""
        return await semantic.get_data_dictionary(manager, server_id, database_id, schema, table, include_statistics)

    # Register internal module API for inter-module communication
    if registry is not None:
        registry.register_module_api("SupersetModule", get_module_api())
