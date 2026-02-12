# Superset Module

This module provides tools for interacting with Apache Superset servers, allowing you to list, inspect, transfer, create, and retrieve data from resources like dashboards, charts, and datasets.

## Available Tools

*   `list_superset_servers()`: Lists all configured Superset servers.
*   `superset_server_status(server_id: str)`: Checks the status and connectivity of a specific Superset server.
*   `superset_available_resource_types()`: Lists all resource types that can be used with `superset_list_resources`.
*   `superset_list_resources(server_id: str, resource_type: str)`: Lists resources of a specific type (e.g., 'dashboard', 'chart').
*   `list_dashboards(server_id: str)`: Lists dashboards on a specific server to get their IDs. (Alias for `superset_list_resources` for 'dashboard' type).
*   `superset_get_resource(server_id: str, resource_type: str, resource_id: Union[int, str])`: Gets details for a specific resource by ID.
*   `superset_get_chart_data(server_id: str, chart_id: int)`: Retrieves the actual data associated with a specific chart.
*   `superset_get_chart_api_info(server_id: str)`: Retrieves metadata about the chart API from the `/api/v1/chart/_info` endpoint.
*   `superset_api_request(server_id: str, method: str, endpoint: str, json_body: Optional[str] = None, params: Optional[str] = None)`: Executes a raw API request against a Superset server.
*   `superset_create_chart(server_id: str, slice_name: str, viz_type: str, datasource_id: int, datasource_type: str, params: str, description: Optional[str] = None)`: Creates a new chart (slice) on a Superset server.
*   `superset_generate_simple_dashboard_layout(chart_ids: List[int], layout_type: str = "row_of_charts", chart_width: int = 6, chart_height: int = 50)`: Generates a basic `position_json` for a dashboard, arranging charts in a simple grid.
*   `superset_create_dashboard(server_id: str, dashboard_title: str, position_json: str, slug: Optional[str] = None, json_metadata: Optional[str] = None, owners: Optional[List[int]] = None, roles: Optional[List[int]] = None, published: Optional[bool] = False)`: Creates a new dashboard on a Superset server.
*   `superset_transfer_item(source_server_id: str, target_server_id: str, resource_type: str, item_id: Union[int, str])`: Transfers a specific item (Chart, Dashboard, etc.) from one server to another.
*   `transfer_dashboard(source_server_id: str, target_server_id: str, dashboard_id: int)`: Transfers a dashboard (and its charts) from a source to a target server. (Alias for `superset_transfer_item` for 'dashboard' type).
*   `superset_reauthenticate(server_id: str)`: Forces re-authentication with a Superset server, obtaining a new access token.

## Authentication and Token Management

The Superset Module handles authentication automatically. When you make a request to a Superset server, the module will:

1.  **Load existing token**: Attempt to load a previously saved access token from disk.
2.  **Authenticate**: If no token is found or is invalid, it will perform a fresh authentication using the credentials configured for the `server_id` (in `servers.json`).
3.  **Save token**: If authentication is successful, the new access token is saved to disk for future use.

### Automatic Token Refresh (Implicit Re-authentication)

The `execute_request` function, which underlies all API calls, includes a robust mechanism for handling expired or invalid tokens:

*   If a Superset API call returns a `401 Unauthorized` status, the module automatically attempts to re-authenticate with the server.
*   It clears the old, invalid token, performs a fresh login, obtains a new access token, updates the client headers, and then retries the original request *once*.
*   This ensures that most token expiration issues are handled seamlessly without manual intervention.

### Manual Re-authentication (Explicit Re-authentication)

While automatic token refresh covers most scenarios, there might be cases where you want to explicitly force a re-login (e.g., if you changed credentials, or suspect an issue before an API call fails).

Use the `superset_reauthenticate` tool for this purpose:

```python
superset_reauthenticate(server_id='your_server_id')
```

This tool will clear any existing token for the specified server and perform a fresh authentication, updating the module's internal state and saved token.

## Extracting Data from Superset

You can extract various data and metadata from your Superset instances using the following workflow:

1.  **List Resources**: Use `superset_list_resources` or `list_dashboards` to get a list of available dashboards, charts, datasets, etc., along with their IDs.

    ```python
    # Example: List all dashboards from 'superset_main'
    list_dashboards(server_id='superset_main')

    # Example: List all charts
    superset_list_resources(server_id='superset_main', resource_type='chart')
    ```

2.  **Get Resource Details**: Once you have the ID of a specific resource (e.g., a dashboard or chart), use `superset_get_resource` to fetch its detailed metadata.

    ```python
    # Example: Get details of dashboard with ID 123
    superset_get_resource(server_id='superset_main', resource_type='dashboard', resource_id=123)

    # Example: Get details of chart with ID 45
    superset_get_resource(server_id='superset_main', resource_type='chart', resource_id=45)
    ```

3.  **Get Chart Data**: Use `superset_get_chart_data` to retrieve the actual data generated by a specific chart.

    ```python
    # Example: Get data for chart with ID 45
    superset_get_chart_data(server_id='superset_main', chart_id=45)
    ```

4.  **Getting Chart API Metadata**: Use `superset_get_chart_api_info` to retrieve metadata about the `/api/v1/chart/_info` endpoint. This can be useful for understanding available filters, permissions, and properties for charts.

    ```python
    # Example: Get API metadata for the chart endpoint
    superset_get_chart_api_info(server_id='superset_main')
    ```

4.  **Getting Chart API Metadata**: Use `superset_get_chart_api_info` to retrieve metadata about the `/api/v1/chart/_info` endpoint. This can be useful for understanding available filters, permissions, and properties for charts.

    ```python
    # Example: Get API metadata for the chart endpoint
    superset_get_chart_api_info(server_id='superset_main')
    ```

5.  **Raw API Requests (Advanced)**: For more granular control or to access endpoints not covered by the wrapper functions, use `superset_api_request`. You can specify the HTTP method, endpoint, and optionally provide JSON request bodies or query parameters.

    ```python
    # Example: Get all datasets (similar to list_resources but direct API)
    superset_api_request(server_id='superset_main', method='GET', endpoint='/api/v1/dataset/')

    # Example: POST request to an arbitrary endpoint (replace with actual use case)
    superset_api_request(
        server_id='superset_main',
        method='POST',
        endpoint='/api/v1/some_custom_endpoint/',
        json_body='{"key": "value"}'
    )
    ```

6.  **Extracting Database Schema**: Use `superset_get_database_schema` to get a structured overview of tables and their columns within a specific database. This tool leverages Superset's SQL Lab to query `information_schema`.

    ```python
    # Example: Get schema for database ID 1 (e.g., PostgreSQL 'public' schema)
    superset_get_database_schema(server_id='superset_main', database_id=1, schema_name='public')

    # Example: Get schema for database ID 2 (e.g., MySQL 'my_db_name' schema, often same as database name)
    superset_get_database_schema(server_id='superset_main', database_id=2, schema_name='my_db_name')
    ```
    This tool currently supports PostgreSQL, MySQL, and MSSQL databases.

## Creating Resources in Superset

This module provides powerful tools to programmatically create and manage Superset resources. Due to inter-resource dependencies, it's crucial to follow a logical creation order:

1.  **Datasets:** Represent tables or SQL queries from your databases.
2.  **Charts (Slices):** Visualizations built upon datasets.
3.  **Dashboards:** Collections of charts arranged for presentation.

This section provides detailed guidance for creating each resource type.

### Creating Datasets

Use `superset_create_dataset` to register a new dataset in Superset, typically linking to an existing table in a connected database.

**Prerequisites:**
*   A database connection must already be configured in Superset. You can list existing databases using `superset_list_resources(server_id='your_server_id', resource_type='database')`.
*   The `database_id` must correspond to an existing database.
*   The `table_name` and `schema` (if applicable) must refer to an actual table in that database.

```python
superset_create_dataset(
    server_id='superset_main',
    table_name='my_source_table',
    database_id=1,  # Replace with actual database ID
    schema='public', # Optional: specify if your table is in a schema other than default
    owners=[1], # Optional: list of owner IDs
    metrics_json='[{"metric_name": "count", "expression": "COUNT(*)", "metric_type": "count"}]', # Optional: define metrics
    columns_json='[{"column_name": "id", "is_dttm": false, "is_active": true, "type": "BIGINT", "filterable": true}]' # Optional: define columns
)
```

**Important Notes on Dataset `metrics_json` and `columns_json`:**
These JSON strings define the metrics and columns available for the dataset in Superset. While optional for basic table-based datasets (Superset often infers them), providing them gives more control.
The best way to get accurate `metrics_json` and `columns_json` for your desired dataset is to:
1.  Create a dataset manually in the Superset UI.
2.  Save the dataset.
3.  Use `superset_get_resource` on the created dataset (e.g., `superset_get_resource(server_id='your_server_id', resource_type='dataset', resource_id=YOUR_DATASET_ID)`) and extract the `metrics` and `columns` fields.

### Creating Charts

Use `superset_create_chart` to add a new chart (slice) to a Superset server, which must be based on an existing dataset.

**Prerequisites:**
*   An existing dataset with a known `datasource_id`. You can list datasets using `superset_list_resources(server_id='your_server_id', resource_type='dataset')`.

```python
superset_create_chart(
    server_id='superset_main',
    slice_name='My New Programmatic Bar Chart',
    viz_type='bar',
    datasource_id=1,  # Replace with actual dataset ID
    datasource_type='table', # Typically 'table' or 'druid'
    params='{"metrics": ["count"], "groupby": ["category_column"], "viz_type": "bar", "time_range": "Last 7 days"}', # See chart_parameters.md for examples
    description='A programmatically created bar chart based on my_source_table.'
)
```

**Important Notes on Chart `params`:**
The `params` argument is a JSON string that defines the entire visualization configuration. This is highly complex and varies significantly with `viz_type`.
*   **Common Errors ("Error: Empty query?", "This visualization type is not supported.")**: These errors often indicate that the `params` JSON is either malformed, missing crucial configurations for the selected `viz_type`, or references columns/metrics that do not exist in the specified `datasource_id`. Additionally, some `viz_type`s (like `dist_bar`) can be more sensitive or require a very specific `params` structure.
*   **Recommendation:** If encountering issues with a complex `viz_type` (e.g., `dist_bar`), first try a simpler alternative like `viz_type: "bar"` with a minimal `params` structure.
*   For detailed examples and guidance on constructing `params` for various `viz_type`s, please refer to: [Superset Chart Parameters Guide](docs/chart_parameters.md)
*   The most reliable way to get an accurate `params` string for your desired chart is to:
    1.  Create the chart manually in the Superset UI using the target dataset.
    2.  Save the chart.
    3.  Use `superset_get_resource` on the created chart and extract the `params` field.

### Creating Dashboards

Use `superset_create_dashboard` to add a new dashboard to a Superset server, arranging existing charts.

**Prerequisites:**
*   One or more existing charts with known `chartId`s that you want to include in the dashboard. You can list charts using `superset_list_resources(server_id='your_server_id', resource_type='chart')`.

```python
# --- Step 1: Generate position_json using the helper tool ---
# Example: Generate layout for a single chart with ID 123
# The generated JSON can be printed to inspect its structure.
generated_position_json = await superset_generate_simple_dashboard_layout(
    server_id='superset_main', # Pass server_id
    chart_ids=[123],
    layout_type="row_of_charts"
)

# Example: Generate layout for multiple charts (IDs 123, 124, 125)
# generated_position_json_multi = await superset_generate_simple_dashboard_layout(
#     server_id='superset_main', # Pass server_id
#     chart_ids=[123, 124, 125],
#     layout_type="row_of_charts",
#     chart_width=6 # Two charts per row
# )
# print(generated_position_json_multi)

# --- Step 2: Use the generated position_json to create the dashboard ---
superset_create_dashboard(
    server_id='superset_main',
    dashboard_title='My New Programmatic Dashboard',
    position_json=generated_position_json, # Use the JSON generated by the helper tool
    slug='my-new-programmatic-dashboard-generated',
    published=True
)
```

**Important Notes on Dashboard `position_json` and `json_metadata`:**
These JSON strings define the layout, chart positioning, and metadata of the dashboard. They are highly complex.
*   **Common Error (TypeError: can't access property "children", dashboard stuck on infinite loading):** This error typically occurs when the `position_json` is malformed or incomplete. Superset's frontend expects a specific hierarchical structure (e.g., `ROOT_ID` containing `GRID_ID` which then contains charts). If this structure is broken or missing elements, the dashboard will fail to render, often resulting in a blank page or an infinite loading spinner.
*   **To prevent these errors for simple layouts, use the `superset_generate_simple_dashboard_layout` tool.** This tool will construct a basic but valid `position_json` for you based on a list of chart IDs, arranging them in a predictable grid.
*   **"There is no chart definition associated..."**: This error occurs when a `chartId` referenced within your `position_json` does not correspond to an existing chart in Superset, or if the `meta` object for a chart component is incorrectly defined. Ensure all `chartId` values in `position_json` refer to valid, existing charts.
*   **For complex layouts, the most reliable way to get accurate `position_json` and `json_metadata` strings is to:**
    1.  Create a dashboard manually in the Superset UI with your desired layout and elements.
    2.  Save the dashboard.
    3.  Inspect the network request payload in your browser's developer tools during the save operation, or use `superset_get_resource` on the created dashboard and extract the `position_json` and `json_metadata` fields.