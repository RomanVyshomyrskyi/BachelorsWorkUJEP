# Superset Module

This module provides tools for interacting with Apache Superset servers, allowing you to list, inspect, transfer, create, and retrieve data from resources like dashboards, charts, and datasets.

---

## Detailed Functionality Reference

### Server Management (`tools/server.py`)

#### `list_superset_servers()`
- **What it does**: Lists all configured Superset servers with their base URLs and authentication methods.
- **How it does it**: Iterates through the contexts stored in the `ConnectionManager`. It performs a hot-reload check on `servers.json` if no servers are currently loaded.

#### `superset_reauthenticate(server_id)`
- **What it does**: Forces a fresh login to obtain a new access token.
- **How it does it**: Clears the `access_token` in the server's context and triggers the `authenticate()` process in `api_client.py`, which performs a POST request to the provider (DB or Keycloak).

#### `superset_server_status(server_id)`
- **What it does**: Verifies connectivity and identifies the authenticated user.
- **How it does it**: Executes a GET request to the `/api/v1/me/` endpoint. If successful, it parses the JSON response to return the username.

### Resource Discovery (`tools/resources.py`)

#### `superset_list_resources(server_id, resource_type)`
- **What it does**: Lists items of a specific type (e.g., `dashboard`, `chart`, `dataset`, `database`).
- **How it does it**: Uses the `RESOURCE_ENDPOINTS` mapping in `models.py` to determine the correct base URL and performs a GET request to `/api/v1/{resource_type}/`.

#### `superset_get_resource(server_id, resource_type, resource_id)`
- **What it does**: Retrieves the full JSON detail of a specific resource.
- **How it does it**: Performs a GET request to `/api/v1/{resource_type}/{resource_id}`.

### Resource Creation and Modification

#### `superset_create_chart(server_id, ...)`
- **What it does**: Creates a new visualization (slice) on the target server.
- **How it does it**: Sends a POST request to `/api/v1/chart/` with a payload containing the slice name, visualization type, and mandatory `params` JSON.

#### `superset_create_dataset(server_id, ...)`
- **What it does**: Registers a new database table as a Superset dataset.
- **How it does it**: Sends a POST request to `/api/v1/dataset/`. It first verifies the existence of the target `database_id` using a detail lookup.

#### `superset_create_dashboard(server_id, ...)`
- **What it does**: Creates a new dashboard with a specified layout.
- **How it does it**: Sends a POST request to `/api/v1/dashboard/`. It accepts a `position_json` string which defines the layout hierarchy.

#### `superset_bulk_link_charts_to_dashboard(server_id, dashboard_id, chart_ids)`
- **What it does**: Associates multiple charts with a specific dashboard in one operation.
- **How it does it**: Executes sequential PUT requests to `/api/v1/chart/{id}` for each chart ID, updating their `dashboards` metadata field.

### SQL Lab and Schema Extraction (`tools/sqllab.py`, `tools/datasets.py`)

#### `superset_sqllab_execute_query(server_id, database_id, sql_query, ...)`
- **What it does**: Executes a SQL query via Superset's SQL Lab.
- **How it does it**: Sends a POST request to `/api/v1/sqllab/execute/`. It returns a `client_id` which must be used to fetch results asynchronously.

#### `superset_get_database_schema(server_id, database_id, schema_name)`
- **What it does**: Returns a structured overview of all tables and columns in a database.
- **How it does it**:
    1. Fetches database details to identify the engine (Postgres, MySQL, or MSSQL).
    2. Executes a SQL Lab query against `information_schema.tables` to list tables.
    3. For each table, executes another SQL Lab query against `information_schema.columns`.
    4. Aggregates the results into a single JSON schema representation.

### Migration and Transfer (`tools/transfer.py`)

#### `transfer_dashboard(source_server_id, target_server_id, dashboard_id)`
- **What it does**: Copies a dashboard and its charts between servers.
- **How it does it**: 
    1. **Export**: Calls GET `/api/v1/dashboard/export/?q=[id]` on the source server to get a ZIP archive.
    2. **Import**: Calls POST `/api/v1/dashboard/import/` on the target server, uploading the ZIP content as multipart form data.

### Expert Rules and Layouts (`rules.py`)

#### `superset_generate_robust_dashboard_layout(server_id, chart_ids)`
- **What it does**: Builds a valid `position_json` hierarchy.
- **How it does it**: Constructs a nested dictionary tree: `ROOT` -> `GRID` -> `ROW` -> `CHART`. This prevents the "length of undefined" errors often seen when charts are placed directly under the grid.

#### `superset_get_standard_chart_params(viz_type, datasource_id, ...)`
- **What it does**: Generates safe defaults for chart parameters.
- **How it does it**: Maps generic names (e.g., 'line') to correct ECharts plugin IDs (e.g., `echarts_timeseries_line`) and ensures mandatory fields like `time_grain_sqla` and `x_axis` are present.

---

## Developer Documentation: Internal Architecture

### `api_client.py`: Request Lifecycle
- **`execute_request()`**: The primary entry point for all API calls. It automatically handles **401 Unauthorized** responses by clearing the invalid token, re-authenticating with the provider, and retrying the request once.
- **`ensure_auth()`**: Checks if a token exists in the current `SupersetContext`. If not, it attempts to load a saved token from `.tokens/` or calls `authenticate()`.

### `manager.py`: Connection Management
- **`ConnectionManager`**: Responsible for loading `servers.json` and initializing `httpx.AsyncClient` instances for each server. It manages separate `.tokens/` files to ensure persistence across sessions.

### `models.py`: Resource Mapping
- **`RESOURCE_ENDPOINTS`**: A centralized dictionary mapping friendly resource names to their corresponding API base paths.
- **`TRANSFER_STRATEGY`**: Defines whether a resource should be transferred via the `export_import` (ZIP) or `json_copy` (Get detail -> Post Create) method.
