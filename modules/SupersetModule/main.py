import os
import sys
import logging
from typing import Optional, List, Union
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', stream=sys.stderr)
logger = logging.getLogger(__name__)

depends_on = []

def get_module_api():
    return {
        "ConnectionManager": ConnectionManager,
        "api_request": general.impl_superset_api,
        "execute_request": __import__("modules.SupersetModule.api_client", fromlist=["execute_request"]).execute_request,
    }

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    module_dir = os.path.dirname(__file__)
    manager = ConnectionManager(module_dir)
    manager.load_servers()

    @mcp.tool(name="list_superset_servers")
    async def tool_list_servers() -> str:
        """Lists all configured Superset servers."""
        return await server.list_servers(manager)

    @mcp.tool(name="superset_reauthenticate")
    async def tool_reauthenticate(server_id: str) -> str:
        """
        Forces re-authentication with a Superset server, obtaining a new access token.
        Use this if you suspect the current token is expired or invalid.
        """
        return await server.reauthenticate(manager, server_id)

    @mcp.tool(name="superset_server_status")
    async def tool_server_status(server_id: str) -> str:
        """
        Checks the status and connectivity of a specific Superset server.
        """
        return await server.server_status(manager, server_id)

    @mcp.tool(name="superset_available_resource_types")
    async def tool_list_resource_types() -> str:
        """
        Lists all available resource types that can be used with `superset_list_resources` 
        and other resource-specific tools.
        """
        return await resources.list_resource_types()

    @mcp.tool(name="superset_api_request")
    async def tool_superset_api(
        server_id: str,
        method: str,
        endpoint: str,
        json_body: Optional[str] = None,
        params: Optional[str] = None
    ) -> str:
        """
        Executes a raw API request against a Superset server.
        Use this to access GET, POST, or PUT methods from the Superset API.
        DELETE operations are strictly forbidden via this tool.
        
        Args:
            server_id: The ID of the configured server.
            method: GET, POST, or PUT.
            endpoint: The API endpoint (e.g., '/api/v1/chart/' or '/api/v1/dashboard/1').
            json_body: Optional JSON string for the request body.
            params: Optional JSON string for query parameters.
        """
        return await general.superset_api_request(manager, server_id, method, endpoint, json_body, params)

    @mcp.tool(name="superset_list_resources")
    async def tool_list_resources(server_id: str, resource_type: str) -> str:
        """
        Lists resources of a specific type (e.g., 'dashboard', 'chart', 'database').
        Wrapper around GET /api/v1/{resource_type}/.
        """
        return await resources.list_resources(manager, server_id, resource_type)

    @mcp.tool(name="list_dashboards")
    async def tool_list_dashboards(server_id: str) -> str:
        """
        Lists dashboards on a specific server to get their IDs.
        """
        return await resources.list_dashboards(manager, server_id)

    @mcp.tool(name="superset_get_resource")
    async def tool_get_resource(
        server_id: str,
        resource_type: str,
        resource_id: Union[int, str]
    ) -> str:
        """
        Gets details for a specific resource by ID.
        Wrapper around GET /api/v1/{resource_type}/{pk}.
        """
        return await resources.get_resource(manager, server_id, resource_type, resource_id)

    @mcp.tool(name="superset_get_chart_api_info")
    async def tool_get_chart_api_info(server_id: str) -> str:
        """
        Retrieves metadata about the chart API from the GET /api/v1/chart/_info endpoint.
        This includes information about available filters, permissions, and properties
        related to the chart resource.

        Args:
            server_id: The ID of the configured Superset server.
        Returns:
            A JSON string containing the API metadata.
        """
        return await charts.get_chart_api_info(manager, server_id)

    @mcp.tool(name="superset_create_chart")
    async def tool_create_chart(
        server_id: str,
        slice_name: str,
        viz_type: str,
        datasource_id: int,
        datasource_type: str,
        params: str,
        description: Optional[str] = None
    ) -> str:
        """
        Creates a new chart (slice) on a Superset server.
        
        Args:
            server_id: The ID of the configured Superset server.
            slice_name: The name of the new chart.
            viz_type: The visualization type (e.g., 'table', 'bar', 'line').
            datasource_id: The ID of the dataset to base the chart on.
            datasource_type: The type of the datasource (e.g., 'table').
            params: A JSON string representing the chart's visualization parameters.
                    It is highly recommended to generate this by creating a chart
                    in the Superset UI and extracting its 'params' JSON string.
            description: Optional description for the chart.
        """
        return await charts.create_chart(manager, server_id, slice_name, viz_type, datasource_id, datasource_type, params, description)

    @mcp.tool(name="superset_generate_simple_dashboard_layout")
    async def tool_generate_simple_dashboard_layout(
        server_id: str,
        chart_ids: List[int],
        layout_type: str = "row_of_charts",
        chart_width: int = 6,
        chart_height: int = 50
    ) -> str:
        """
        Generates a basic, valid position_json structure for a Superset dashboard,
        arranging a list of charts in a simple layout.

        This helps avoid common TypeError issues from manually crafting complex position_json.
        For more complex layouts, it is still recommended to extract position_json from the UI.

        Args:
            server_id: The ID of the configured Superset server.
            chart_ids: A list of integer IDs of the charts to include in the dashboard.
            layout_type: 'row_of_charts' (default) to arrange charts horizontally,
                         'column_of_charts' to arrange charts vertically.
            chart_width: The width of each chart in Superset's 12-unit grid system.
                         Defaults to 6 (half width).
            chart_height: The height of each chart. Defaults to 50.
        Returns:
            A JSON string representing the generated position_json.
        """
        return await dashboards.generate_simple_dashboard_layout(manager, server_id, chart_ids, layout_type, chart_width, chart_height)

    @mcp.tool(name="superset_create_dashboard")
    async def tool_create_dashboard(
        server_id: str,
        dashboard_title: str,
        position_json: str,
        slug: Optional[str] = None,
        json_metadata: Optional[str] = None,
        owners: Optional[List[int]] = None,
        roles: Optional[List[int]] = None,
        published: Optional[bool] = False
    ) -> str:
        """
        Creates a new dashboard on a Superset server.
        
        Args:
            server_id: The ID of the configured Superset server.
            dashboard_title: The title of the new dashboard.
            position_json: A JSON string defining the layout and positioning of charts
                           within the dashboard. It is highly recommended to generate
                           this by creating a dashboard in the Superset UI and
                           extracting its 'position_json' string.
            slug: Optional URL-friendly identifier for the dashboard.
            json_metadata: Optional JSON string for various dashboard metadata.
            owners: Optional list of owner IDs.
            roles: Optional list of role IDs that have access.
            published: Optional boolean indicating if the dashboard should be published.
        """
        return await dashboards.create_dashboard(manager, server_id, dashboard_title, position_json, slug, json_metadata, owners, roles, published)

    @mcp.tool(name="superset_create_dataset")
    async def tool_create_dataset(
        server_id: str,
        table_name: str,
        database_id: int,
        schema: Optional[str] = None,
        owners: Optional[List[int]] = None,
        metrics_json: Optional[str] = None,
        columns_json: Optional[str] = None,
        sql_expression: Optional[str] = None
    ) -> str:
        """
        Creates a new dataset on a Superset server.
        
        Args:
            server_id: The ID of the configured Superset server.
            table_name: The name of the table in the database that this dataset will represent.
            database_id: The ID of the database where the table resides.
            schema: Optional schema name if your database uses schemas.
            owners: Optional list of user IDs who own the dataset.
            metrics_json: Optional JSON string of metric definitions for the dataset.
            columns_json: Optional JSON string of column definitions for the dataset.
            sql_expression: Optional SQL query for virtual datasets.
        """
        return await datasets.create_dataset(manager, server_id, table_name, database_id, schema, owners, metrics_json, columns_json, sql_expression)

    @mcp.tool(name="superset_sqllab_execute_query")
    async def tool_sqllab_execute_query(
        server_id: str,
        database_id: int,
        sql_query: str,
        schema: Optional[str] = None,
        client_id: Optional[str] = None,
        tab_name: Optional[str] = None
    ) -> str:
        """
        Executes an SQL query through Superset's SQL Lab API.
        
        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database to execute the query against.
            sql_query: The SQL query string to execute.
            schema: Optional schema to use for the query.
            client_id: Optional client ID for the query. If not provided, one will be generated by Superset.
            tab_name: Optional tab name for the query.
        """
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema, client_id, tab_name)

    @mcp.tool(name="superset_sqllab_get_query_results")
    async def tool_sqllab_get_query_results(
        server_id: str,
        client_id: str
    ) -> str:
        """
        Retrieves the results of a previously executed SQL Lab query.
        
        Args:
            server_id: The ID of the configured Superset server.
            client_id: The client ID of the query whose results are to be retrieved.
        """
        return await sqllab.sqllab_get_query_results(manager, server_id, client_id)

    @mcp.tool(name="transfer_dashboard")
    async def tool_transfer_dashboard(
        source_server_id: str,
        target_server_id: str,
        dashboard_id: int,
        db_mappings: Optional[str] = None,
        table_mappings: Optional[str] = None
    ) -> str:
        """
        Transfers a Dashboard (and its charts) from a source Superset server to a target Superset server.
        Uses a 3-phase approach: datasets -> charts -> dashboard with interactive fallback.
        If a database or table is not found on the target, returns a NEED_INPUT message
        asking the user to provide mappings. Retry with db_mappings/table_mappings JSON.
        """
        return await transfer.transfer_dashboard(manager, source_server_id, target_server_id, dashboard_id, db_mappings, table_mappings)

    @mcp.tool(name="superset_get_database_schema")
    async def tool_get_database_schema(
        server_id: str,
        database_id: int,
        schema_name: Optional[str] = None
    ) -> str:
        """
        Retrieves the schema (tables and columns) for a specified database on a Superset server
        by querying the database's information_schema via SQL Lab.

        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database to inspect.
            schema_name: Optional schema name to filter tables (e.g., 'public' for PostgreSQL).
        """
        return await datasets.get_database_schema(manager, server_id, database_id, schema_name)

    @mcp.tool(name="superset_get_dashboard_api_info")
    async def tool_get_dashboard_api_info(server_id: str) -> str:
        """
        Retrieves metadata about the dashboard API from the GET /api/v1/dashboard/_info endpoint.
        Useful for understanding available fields and validation rules for dashboards.
        """
        return await dashboards.get_dashboard_api_info(manager, server_id)

    @mcp.tool(name="superset_update_chart")
    async def tool_update_chart(
        server_id: str,
        chart_id: int,
        json_body: str
    ) -> str:
        """
        Updates an existing chart on a Superset server.
        Args:
            server_id: The ID of the configured server.
            chart_id: The ID of the chart to update.
            json_body: A JSON string containing the fields to update (e.g., '{"params": "...", "dashboards": [1]}').
        """
        return await charts.update_chart(manager, server_id, chart_id, json_body)

    @mcp.tool(name="superset_update_dashboard")
    async def tool_update_dashboard(
        server_id: str,
        dashboard_id: int,
        json_body: str
    ) -> str:
        """
        Updates an existing dashboard on a Superset server.
        Args:
            server_id: The ID of the configured server.
            dashboard_id: The ID of the dashboard to update.
            json_body: A JSON string containing the fields to update (e.g., '{"dashboard_title": "New Title"}').
        """
        return await dashboards.update_dashboard(manager, server_id, dashboard_id, json_body)

    @mcp.tool(name="superset_bulk_link_charts_to_dashboard")
    async def tool_bulk_link_charts(
        server_id: str,
        dashboard_id: int,
        chart_ids: List[int]
    ) -> str:
        """
        Links multiple charts to a dashboard in bulk.
        This is necessary because charts must be explicitly associated with a dashboard
        in the database to appear, even if they are in the position_json.
        """
        return await dashboards.bulk_link_charts(manager, server_id, dashboard_id, chart_ids)

    @mcp.tool(name="superset_generate_robust_dashboard_layout")
    async def tool_generate_robust_layout(
        server_id: str,
        chart_ids: List[int]
    ) -> str:
        """
        Generates a robust, nested position_json for Superset dashboards.
        Uses a proper ROOT -> GRID -> ROW -> CHART hierarchy to avoid TypeError.
        """
        return await dashboards.generate_robust_layout(manager, server_id, chart_ids)

    @mcp.tool(name="superset_get_standard_chart_params")
    def tool_get_standard_params(
        viz_type: str,
        datasource_id: int,
        overrides_json: Optional[str] = None
    ) -> str:
        """
        Returns a JSON string of standard parameters for a given visualization type.
        Helps prevent 'empty query' errors by providing mandatory fields.
        """
        return charts.get_standard_chart_params(viz_type, datasource_id, overrides_json)

    @mcp.tool(name="superset_get_chart_creation_rules")
    def tool_get_chart_rules() -> str:
        """Returns the expert rules for creating functional Superset charts."""
        return charts.get_chart_creation_rules()

    @mcp.tool(name="superset_get_dashboard_creation_rules")
    def tool_get_dashboard_rules() -> str:
        """Returns the expert rules for creating functional Superset dashboards."""
        return dashboards.get_dashboard_creation_rules()

    @mcp.tool(name="list_charts")
    async def tool_list_charts(server_id: str) -> str:
        """
        Lists all charts on a Superset server to get their IDs.
        Wrapper around GET /api/v1/chart/.
        """
        return await charts.list_charts(manager, server_id)

    @mcp.tool(name="get_chart_info")
    async def tool_get_chart_info(
        server_id: str,
        chart_id: Union[int, str]
    ) -> str:
        """
        Gets detailed information for a specific chart by ID.
        
        Args:
            server_id: The ID of the configured Superset server.
            chart_id: The ID of the chart to retrieve.
        """
        return await charts.get_chart_info(manager, server_id, chart_id)

    @mcp.tool(name="list_databases")
    async def tool_list_databases(server_id: str) -> str:
        """
        Lists all database connections on a Superset server.
        Wrapper around GET /api/v1/database/.
        """
        return await databases.list_databases(manager, server_id)

    @mcp.tool(name="get_database_info")
    async def tool_get_database_info(
        server_id: str,
        database_id: int
    ) -> str:
        """
        Gets detailed information for a specific database connection by ID.
        
        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database to retrieve.
        """
        return await databases.get_database_info(manager, server_id, database_id)

    @mcp.tool(name="list_datasets")
    async def tool_list_datasets(server_id: str) -> str:
        """
        Lists all datasets on a Superset server.
        Wrapper around GET /api/v1/dataset/.
        """
        return await datasets.list_datasets(manager, server_id)

    @mcp.tool(name="get_dataset_info")
    async def tool_get_dataset_info(
        server_id: str,
        dataset_id: Union[int, str]
    ) -> str:
        """
        Gets detailed information for a specific dataset by ID.
        
        Args:
            server_id: The ID of the configured Superset server.
            dataset_id: The ID of the dataset to retrieve.
        """
        return await datasets.get_dataset_info(manager, server_id, dataset_id)

    @mcp.tool(name="get_dashboard_info")
    async def tool_get_dashboard_info(
        server_id: str,
        dashboard_id: Union[int, str]
    ) -> str:
        """
        Gets detailed information for a specific dashboard by ID.
        
        Args:
            server_id: The ID of the configured Superset server.
            dashboard_id: The ID of the dashboard to retrieve.
        """
        return await dashboards.get_dashboard_info(manager, server_id, dashboard_id)

    # === Official Apache MCP tool names ===

    @mcp.tool(name="generate_chart")
    async def tool_generate_chart(
        server_id: str,
        dataset_id: int,
        config: str,
        slice_name: Optional[str] = None,
        save_chart: bool = True,
        description: Optional[str] = None
    ) -> str:
        """Create and optionally save a new chart.
        
        Use generate_explore_link for exploration (no permanent chart created).
        Use generate_chart with save_chart=True only when the user wants to save.
        
        Args:
            server_id: The ID of the configured Superset server.
            dataset_id: The ID of the dataset to base the chart on.
            config: JSON string of chart configuration (viz_type, metrics, etc.).
            slice_name: Optional name for the chart.
            save_chart: If True, saves permanently. If False, returns preview only.
            description: Optional description.
        """
        return await charts.generate_chart(manager, server_id, dataset_id, config, slice_name, save_chart, description)

    @mcp.tool(name="get_chart_preview")
    async def tool_get_chart_preview(
        server_id: str,
        chart_id: Union[int, str]
    ) -> str:
        """Get a visual preview of a chart with image URL.
        
        Returns a URL to a PNG preview image of the chart.
        
        Args:
            server_id: The ID of the configured Superset server.
            chart_id: The ID of the chart to preview.
        """
        return await charts.get_chart_preview(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_data")
    async def tool_get_chart_data(
        server_id: str,
        chart_id: Union[int, str]
    ) -> str:
        """Get underlying chart data in text-friendly format.
        
        Returns the raw data that backs the chart.
        
        Args:
            server_id: The ID of the configured Superset server.
            chart_id: The ID of the chart.
        """
        return await charts.get_chart_data(manager, server_id, chart_id)

    @mcp.tool(name="get_chart_type_schema")
    async def tool_get_chart_type_schema(
        server_id: str,
        chart_type: str
    ) -> str:
        """Get schema for a specific chart type.
        
        Returns expected parameters and configuration for a visualization type.
        
        Args:
            server_id: The ID of the configured Superset server.
            chart_type: The visualization type (e.g., 'xy', 'big_number', 'table').
        """
        return await charts.get_chart_type_schema(manager, server_id, chart_type)

    @mcp.tool(name="generate_dashboard")
    async def tool_generate_dashboard(
        server_id: str,
        dashboard_title: str,
        chart_ids: List[int],
        slug: Optional[str] = None,
        json_metadata: Optional[str] = None,
        published: bool = False,
        layout_type: str = "robust"
    ) -> str:
        """Create a new dashboard from chart IDs.
        
        Automatically generates the dashboard layout from the provided chart IDs.
        Preferred over superset_create_dashboard when you have chart IDs.
        
        Args:
            server_id: The ID of the configured Superset server.
            dashboard_title: The title for the new dashboard.
            chart_ids: List of chart IDs to include.
            slug: Optional URL-friendly identifier.
            json_metadata: Optional JSON string for metadata.
            published: Whether the dashboard should be published.
            layout_type: Layout style ('robust' or 'simple').
        """
        return await dashboards.generate_dashboard(manager, server_id, dashboard_title, chart_ids, slug, json_metadata, published, layout_type)

    @mcp.tool(name="add_chart_to_existing_dashboard")
    async def tool_add_chart_to_existing_dashboard(
        server_id: str,
        dashboard_id: int,
        chart_id: int
    ) -> str:
        """Add a chart to an existing dashboard.
        
        Preferred tool for adding charts to EXISTING dashboards.
        Only use generate_dashboard to create a brand-new dashboard.
        
        Args:
            server_id: The ID of the configured Superset server.
            dashboard_id: The ID of the existing dashboard.
            chart_id: The ID of the chart to add.
        """
        return await dashboards.add_chart_to_existing_dashboard(manager, server_id, dashboard_id, chart_id)

    @mcp.tool(name="create_virtual_dataset")
    async def tool_create_virtual_dataset(
        server_id: str,
        dataset_name: str,
        database_id: int,
        sql: str,
        schema: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """Save a SQL query as a virtual dataset for charting.
        
        Creates a virtual dataset from a SQL query that can be used to create charts.
        
        Args:
            server_id: The ID of the configured Superset server.
            dataset_name: Name for the virtual dataset.
            database_id: The ID of the database.
            sql: The SQL query for the virtual dataset.
            schema: Optional schema name.
            description: Optional description.
        """
        return await datasets.create_virtual_dataset(manager, server_id, dataset_name, database_id, sql, schema, description)

    @mcp.tool(name="generate_explore_link")
    async def tool_generate_explore_link(
        server_id: str,
        dataset_id: int,
        config: Optional[str] = None
    ) -> str:
        """Generate an interactive explore URL for ad-hoc data exploration.
        
        Creates a URL that opens Superset's Explore view with pre-configured
        chart settings. Does NOT create a permanent chart.
        
        Args:
            server_id: The ID of the configured Superset server.
            dataset_id: The ID of the dataset to explore.
            config: Optional JSON string of chart configuration.
        """
        return await explore.generate_explore_link(manager, server_id, dataset_id, config)

    @mcp.tool(name="execute_sql")
    async def tool_execute_sql(
        server_id: str,
        database_id: int,
        sql_query: str,
        schema: Optional[str] = None
    ) -> str:
        """Execute SQL queries and get results (requires database_id).
        
        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database.
            sql_query: The SQL query string to execute.
            schema: Optional schema name.
        """
        return await sqllab.sqllab_execute_query(manager, server_id, database_id, sql_query, schema)

    @mcp.tool(name="save_sql_query")
    async def tool_save_sql_query(
        server_id: str,
        database_id: int,
        label: str,
        sql: str,
        schema: Optional[str] = None,
        description: Optional[str] = None
    ) -> str:
        """Save a SQL query to Saved Queries list.
        
        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database.
            label: The name/label for the saved query.
            sql: The SQL query text to save.
            schema: Optional schema name.
            description: Optional description.
        """
        return await sqllab.save_sql_query(manager, server_id, database_id, label, sql, schema, description)

    @mcp.tool(name="open_sql_lab_with_context")
    async def tool_open_sql_lab_with_context(
        server_id: str,
        database_id: int,
        sql: Optional[str] = None,
        schema: Optional[str] = None
    ) -> str:
        """Generate SQL Lab URL with pre-filled sql.
        
        Args:
            server_id: The ID of the configured Superset server.
            database_id: The ID of the database.
            sql: Optional pre-filled SQL query.
            schema: Optional schema name.
        """
        return await sqllab.open_sql_lab_with_context(manager, server_id, database_id, sql, schema)

    @mcp.tool(name="get_schema")
    async def tool_get_schema(
        server_id: str,
        model_type: Optional[str] = None
    ) -> str:
        """Get schema metadata for chart/dataset/dashboard (columns, filters).
        
        Returns filterable columns, sortable columns, default columns.
        Use this before calling list_* tools to discover available filters.
        
        Args:
            server_id: The ID of the configured Superset server.
            model_type: Optional type ('chart', 'dataset', 'dashboard', 'database').
        """
        return await system.get_schema(manager, server_id, model_type)

    @mcp.tool(name="get_instance_info")
    async def tool_get_instance_info(server_id: str) -> str:
        """Get instance-wide statistics, metadata, and current user identity.
        
        Call this first after connecting to learn the user's identity
        and available features.
        
        Args:
            server_id: The ID of the configured Superset server.
        """
        return await system.get_instance_info(manager, server_id)

    if registry is not None:
        registry.register_module_api("SupersetModule", get_module_api())
