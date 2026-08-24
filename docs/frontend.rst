Frontend API Reference
======================

This section documents the TypeScript/React frontend application for the Superset Dashboard Manager.

.. note::
   The frontend is built with React, TypeScript, and Vite. Source code is located in ``frontend/src/``.

Project Structure
-----------------

::

   frontend/src/
   ├── api/
   │   └── service.ts          # API service for backend communication
   ├── components/
   │   ├── Navbar.tsx           # Navigation bar component
   │   ├── SummaryCards.tsx     # Export summary statistics cards
   │   ├── ExportResults.tsx    # Detailed export results display
   │   └── ImportResults.tsx    # Import readiness validation display
   ├── pages/
   │   ├── DashboardPage.tsx    # Main dashboard export/import page
   │   └── SettingsPage.tsx     # Server configuration settings page
   ├── types/
   │   └── index.ts             # TypeScript type definitions
   ├── styles/
   │   └── global.css           # Global CSS styles and design tokens
   ├── App.tsx                  # Root application component with routing
   ├── main.tsx                 # Application entry point
   └── vite-env.d.ts            # Vite environment type declarations

API Service
-----------

.. py:module:: api.service

The API service module handles all communication with the backend MCP server.

.. py:function:: getBackendUrl() -> str

   Determines the backend API URL based on environment configuration.

   Priority order:

   1. ``VITE_BACKEND_URL`` from environment variables
   2. ``http://host.docker.internal:8000`` when running on port 8080 or in dev mode
   3. Empty string (relative URL) for production behind a reverse proxy

   :returns: The resolved backend base URL.
   :rtype: str

.. py:function:: buildQueryString(params: dict) -> str

   Serializes query parameters into a URL-encoded query string.

   Handles null/undefined filtering and JSON-stringifies object values.

   :param dict params: Key-value pairs of query parameters.
   :returns: A URL-encoded query string (e.g., ``"key1=value1&key2=value2"``).
   :rtype: str

   **Example:**

   .. code-block:: python

      buildQueryString({"server_id": "prod", "dashboard_id": 42})
      # Returns "server_id=prod&dashboard_id=42"

.. py:function:: callTool(toolName: str, params: dict, usePost: bool = False) -> dict

   Sends an HTTP request to a backend tool endpoint.

   Routes requests to GET (with query string) or POST (with JSON body)
   based on the ``usePost`` flag. Automatically parses double-encoded JSON
   responses from the backend.

   :param str toolName: The name of the backend tool/endpoint (e.g., ``"get_dashboard_expert_info"``).
   :param dict params: Parameters to pass. For GET: query params. For POST: JSON body.
   :param bool usePost: Whether to use POST (True) or GET (False) method.
   :returns: The parsed JSON response from the backend.
   :rtype: dict
   :raises Error: If the HTTP response is not OK.

   **Example:**

   .. code-block:: python

      # GET request
      result = await callTool("list_dashboards", {"server_id": "prod"})

      # POST request
      result = await callTool("validate_export_file", {
          "target_server_id": "staging",
          "export_data": json.dumps(exportData),
      }, usePost=True)

.. py:function:: parseDoubleEncoded(data: Any) -> Any

   Recursively parses double-encoded JSON strings in an object.

   The backend sometimes returns JSON strings that are themselves
   JSON-encoded. This function detects string values that are valid
   JSON and parses them into native objects.

   :param data: The data to parse (string, object, or other).
   :returns: The parsed data with string values attempted to be JSON-decoded.

API Object Methods
~~~~~~~~~~~~~~~~~~

.. py:class:: api

   Frontend API service module for communicating with the backend MCP server.

   .. py:method:: exportDashboard(serverId: str, dashboardId: int) -> ExportResult

      Exports detailed information about a Superset dashboard including charts,
      datasets, databases, and SQL queries.

      :param str serverId: The ID of the Superset server to query.
      :param int dashboardId: The numeric ID of the dashboard to export.
      :returns: Full export result containing dashboard metadata, charts, datasets, databases, tables, and SQL queries.
      :rtype: ExportResult

      **Example:**

      .. code-block:: typescript

         const result = await api.exportDashboard('production', 10);
         console.log(result.dashboard.name);       // "Sales Overview"
         console.log(result.summary.total_charts); // 5

   .. py:method:: checkImportReady(targetServerId: str, exportData: str) -> ImportCheckResult

      Validates whether an exported dashboard can be safely imported into a target server.

      Checks for missing databases, datasets, and chart issues that would block
      the import. Returns a detailed report with blockers and recommendations.

      :param str targetServerId: The ID of the target Superset server for import.
      :param str exportData: JSON string of the export data to validate.
      :returns: Import check result with can_import flag, detailed checks, blockers, and recommendations.
      :rtype: ImportCheckResult

      **Example:**

      .. code-block:: typescript

         const result = await api.checkImportReady('staging', JSON.stringify(exportData));
         if (result.can_import) {
             console.log('Safe to import');
         } else {
             result.blockers.forEach(b => console.log('Blocker:', b));
         }

   .. py:method:: listServers() -> str[]

      Retrieves a list of configured server IDs from the backend.

      :returns: Array of server ID strings.
      :rtype: list[str]

      **Example:**

      .. code-block:: typescript

         const servers = await api.listServers();
         // Returns: ["production", "staging", "development"]

   .. py:method:: getBackendServerConfigs() -> dict

      Fetches full configuration objects for all backend servers.

      :returns: Record mapping server IDs to their configuration (base_url, auth_method).
      :rtype: dict

   .. py:method:: listDashboards(serverId: str) -> DashboardItem[]

      Lists all available dashboards for a given Superset server.

      :param str serverId: The ID of the Superset server to query.
      :returns: Array of dashboard items containing id and dashboard_title.
      :rtype: list[DashboardItem]

      **Example:**

      .. code-block:: typescript

         const dashboards = await api.listDashboards('production');
         // Returns: [{ id: 10, dashboard_title: "Sales Overview" }]

   .. py:method:: loadConfig() -> AppConfig

      Loads the application configuration from localStorage.

      Falls back to default configuration (backend host: localhost, port: 8000,
      no Superset servers) if no stored config exists.

      :returns: The application configuration.
      :rtype: AppConfig

   .. py:method:: saveConfig(config: AppConfig) -> None

      Saves the application configuration to localStorage.

      :param AppConfig config: The complete application configuration to persist.

Type Definitions
----------------

.. py:module:: types

TypeScript interfaces defining the data structures used throughout the application.

.. py:class:: SupersetServerConfig

   Configuration for a Superset server managed by the application.

   .. py:attribute:: id: str

      Unique identifier for the server (e.g., ``"production"``, ``"staging"``).

   .. py:attribute:: name: str

      Human-readable display name for the server.

   .. py:attribute:: host: str

      The hostname or IP address of the Superset server.

   .. py:attribute:: port: int

      The port number the Superset server is running on.

   .. py:attribute:: enabled: bool

      Whether this server is active and available for use.

.. py:class:: DashboardItem

   A minimal representation of a Superset dashboard for listing purposes.

   .. py:attribute:: id: int

      The numeric ID of the dashboard in Superset.

   .. py:attribute:: dashboard_title: str

      The display title of the dashboard.

.. py:class:: ChartInfo

   Detailed information about a Superset chart within a dashboard.

   .. py:attribute:: id: int

      The numeric ID of the chart in Superset.

   .. py:attribute:: name: str

      The display name of the chart.

   .. py:attribute:: viz_type: str

      The visualization type (e.g., ``"bar"``, ``"line"``, ``"pie"``, ``"table"``).

   .. py:attribute:: datasource_id: int, optional

      The ID of the datasource this chart uses.

   .. py:attribute:: datasource_type: str, optional

      The type of datasource (e.g., ``"table"``, ``"query"``).

   .. py:attribute:: sql_in_params: list[str]

      Array of SQL query parameters associated with the chart.

.. py:class:: DatasetInfo

   Information about a Superset dataset (physical table or virtual SQL query).

   .. py:attribute:: id: int

      The numeric ID of the dataset in Superset.

   .. py:attribute:: name: str

      The display name of the dataset.

   .. py:attribute:: type: str

      Whether this is a physical table or a virtual SQL query dataset (``"virtual"`` | ``"physical"``).

   .. py:attribute:: database_id: int, optional

      The ID of the database this dataset belongs to.

   .. py:attribute:: schema: str, optional

      The database schema (e.g., ``"public"``, ``"analytics"``).

   .. py:attribute:: table_name: str

      The table name (for physical datasets) or alias (for virtual).

   .. py:attribute:: columns: list[dict]

      Array of column definitions with name and type.

   .. py:attribute:: metrics: list[dict]

      Array of metric definitions with name and SQL expression.

   .. py:attribute:: sql: str, optional

      The SQL query for virtual datasets (undefined for physical).

.. py:class:: DatabaseInfo

   Information about a database connection configured in Superset.

   .. py:attribute:: id: int

      The numeric ID of the database in Superset.

   .. py:attribute:: name: str

      The display name of the database connection.

   .. py:attribute:: engine: str, optional

      The database engine/driver (e.g., ``"postgresql"``, ``"mysql"``).

   .. py:attribute:: sqlalchemy_uri: str, optional

      The SQLAlchemy connection URI for the database.

.. py:class:: ExportResult

   Complete result of a dashboard export operation.

   .. py:attribute:: dashboard: dict

      Core dashboard metadata with id, name, chart_count, and chart_ids.

   .. py:attribute:: charts: list[ChartInfo]

      Array of all charts in the dashboard.

   .. py:attribute:: datasets: list[DatasetInfo]

      Array of all datasets used by the dashboard charts.

   .. py:attribute:: databases: list[DatabaseInfo]

      Array of all databases referenced by the datasets.

   .. py:attribute:: tables: list[str]

      Array of table names referenced by the datasets.

   .. py:attribute:: sql_queries: list[dict]

      Array of SQL queries extracted from charts (chart_id, chart_name, sql).

   .. py:attribute:: summary: dict

      Aggregate counts: total_charts, total_datasets, total_databases, total_tables, total_sql_queries.

.. py:class:: ImportCheckResult

   Result of an import readiness validation check.

   .. py:attribute:: can_import: bool

      Whether the import can proceed without blockers.

   .. py:attribute:: dashboard: dict

      Dashboard metadata from the export (id, name, source_server, chart_count).

   .. py:attribute:: target_server: str

      The ID of the target server being checked.

   .. py:attribute:: checks: dict

      Detailed check results for databases, datasets, and charts.

   .. py:attribute:: summary: dict

      Aggregate counts of checked items and issues.

   .. py:attribute:: blockers: list[str]

      List of critical issues that would prevent import.

   .. py:attribute:: recommendations: list[str]

      List of suggestions to improve import success.

.. py:class:: AppConfig

   Complete application configuration stored in localStorage.

   .. py:attribute:: backend: BackendServerConfig

      Configuration for the backend API server (host, port).

   .. py:attribute:: supersetServers: list[SupersetServerConfig]

      Array of configured Superset servers.

Components
----------

.. py:module:: components

React UI components used throughout the application.

.. py:class:: Navbar

   Navigation bar component with links to Dashboard and Settings pages.

   Uses react-router-dom's ``useLocation`` hook to determine the current
   route and apply an "active" class to the corresponding link.

   **Props:** None

   **Returns:** The navigation bar element.

.. py:class:: SummaryCards

   Summary cards component displaying export statistics.

   Renders a grid of cards showing the count of charts, datasets,
   databases, tables, and SQL queries in the exported dashboard.

   **Props:**

   - ``summary`` (ExportResult['summary']): Summary counts from the export.
   - ``dashboard`` (ExportResult['dashboard']): Dashboard metadata from the export.

   **Example:**

   .. code-block:: typescript

      <SummaryCards
        summary={exportData.summary}
        dashboard={exportData.dashboard}
      />

.. py:class:: ExportResults

   Export results component displaying detailed dashboard export information.

   Renders sections for:

   - Databases: Lists all database connections with their engine type
   - Datasets: Lists all datasets with type and optional schema
   - Charts: Lists all charts with visualization type and SQL query count
   - SQL Queries: Shows up to 5 SQL queries in collapsible details

   **Props:**

   - ``data`` (ExportResult): The full export result to display.

.. py:class:: ImportResults

   Import results component displaying import readiness validation.

   Renders:

   - Header with can_import status badge
   - Summary cards showing pass/fail counts for databases, datasets, and charts
   - Blockers section (red) with critical issues preventing import
   - Recommendations section (yellow) with suggestions
   - Detailed checks section listing each database, dataset, and chart

   **Props:**

   - ``data`` (ImportCheckResult): The import check result to display.

Pages
-----

.. py:module:: pages

Main page components that serve as route targets.

.. py:class:: DashboardPage

   Dashboard management page component with export and import tabs.

   **Features:**

   - Export tab: Select a server and dashboard, export to JSON, download results
   - Import tab: Load a JSON export file, select target server, check import readiness

   **State Variables:**

   - ``servers``: Merged list of custom and backend Superset servers
   - ``selectedServer``: Currently selected source server ID
   - ``dashboards``: List of dashboards on the selected server
   - ``selectedDashboard``: Currently selected dashboard ID
   - ``exportData``: Result of the last export operation
   - ``importCheckData``: Result of the last import readiness check
   - ``loading``: Current loading state
   - ``importFile``: Selected file for import
   - ``importFileData``: Parsed JSON data from the import file
   - ``importTargetServer``: Target server ID for import check
   - ``activeTab``: Currently active tab ('export' | 'import')

   **Methods:**

   - ``loadServers()``: Loads and merges server configurations from localStorage and backend
   - ``loadDashboards(serverId)``: Loads dashboards for the specified server
   - ``handleExport()``: Exports the selected dashboard from the selected server
   - ``handleFileLoad(event)``: Handles file selection for import
   - ``handleImportCheck()``: Checks import readiness for the loaded export file
   - ``downloadJson(data, filename)``: Downloads data as a JSON file

.. py:class:: SettingsPage

   Settings page component for application configuration.

   **Features:**

   - Backend configuration: Edit backend host and port
   - Superset servers: List, add, edit, delete, enable/disable servers
   - Server form: Add new or edit existing server with validation

   **Methods:**

   - ``loadConfig()``: Loads configuration from localStorage and merges with backend server configs
   - ``handleAddServer()``: Resets the form for adding a new server
   - ``handleEditServer(server)``: Populates the form with an existing server's data
   - ``handleDeleteServer(id)``: Deletes a server from the configuration
   - ``handleSaveServer()``: Saves the current form data as a new or updated server
   - ``handleCancel()``: Cancels the add/edit form
   - ``toggleServer(id)``: Toggles the enabled status of a server

Application Entry
-----------------

.. py:module:: App

Root application component with routing and layout.

Configures:

- BrowserRouter for client-side routing
- Toaster for toast notifications (positioned top-right)
- Navbar for navigation
- Routes for Dashboard (``/``) and Settings (``/settings``) pages

.. py:module:: main

Application entry point. Mounts the React app to the DOM root element with StrictMode enabled.

- Mounts to the DOM element with id ``"root"``
- Wraps the app in StrictMode for development-time checks
- Imports global CSS styles

Vite Configuration
------------------

.. py:module:: vite.config

Vite configuration for the React frontend application.

**Server settings:**

- Host: ``0.0.0.0`` (accessible from network/Docker)
- Port: ``3000``
- Proxy: Routes API requests to backend at ``host.docker.internal:8000``

**Proxy rules** (all proxied to ``http://host.docker.internal:8000``):

- ``/get_dashboard_expert_info`` - Export dashboard details
- ``/check_dashboard_import_ready`` - Validate import readiness
- ``/list_superset_servers`` - List configured servers
- ``/list_dashboards`` - List dashboards on a server
- ``/get_server_configs_json`` - Get server configs as JSON array
- ``/get_server_configs_full`` - Get full server configuration objects

Environment Variables
---------------------

.. py:module:: vite-env

Custom environment variables available at build time.

.. py:attribute:: VITE_BACKEND_URL: str

   The base URL of the backend API server.
   Used by ``api/service.ts`` to determine where to send API requests.

   **Example (.env file):**

   .. code-block:: text

      VITE_BACKEND_URL=http://localhost:8000
