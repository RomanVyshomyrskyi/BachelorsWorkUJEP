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
*   `superset_api_request(server_id: str, method: str, endpoint: str, json_body: Optional[str] = None, params: Optional[str] = None)`: Executes a raw API request against a Superset server.
*   `superset_create_chart(server_id: str, slice_name: str, viz_type: str, datasource_id: int, datasource_type: str, params: str, description: Optional[str] = None)`: Creates a new chart (slice) on a Superset server.
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

4.  **Raw API Requests (Advanced)**: For more granular control or to access endpoints not covered by the wrapper functions, use `superset_api_request`. You can specify the HTTP method, endpoint, and optionally provide JSON request bodies or query parameters.

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

## Creating Resources in Superset

The module also provides tools to create new charts and dashboards. Due to the complexity of their configurations, these tools expect pre-formatted JSON strings for certain parameters.

### Creating Charts

Use `superset_create_chart` to add a new chart to a Superset server.

```python
superset_create_chart(
    server_id='superset_main',
    slice_name='My New Bar Chart',
    viz_type='bar',
    datasource_id=1,  # Replace with actual datasource ID
    datasource_type='table',
    params='{"metrics": ["count"], "groupby": ["column_name"], "viz_type": "bar", "time_range": "Last 7 days"}', # Simplified example
    description='A programmatically created bar chart.'
)
```

**Important Note on Chart `params`:**
The `params` argument is a JSON string that defines the entire visualization configuration. This can be very complex and varies significantly with `viz_type`. The best way to get an accurate `params` string for your desired chart is to:
1.  Create the chart manually in the Superset UI.
2.  Save the chart.
3.  Inspect the network request payload in your browser's developer tools during the save operation, or use `superset_get_resource` on the created chart and extract the `params` field.

### Creating Dashboards

Use `superset_create_dashboard` to add a new dashboard to a Superset server.

```python
superset_create_dashboard(
    server_id='superset_main',
    dashboard_title='My New Programmatic Dashboard',
    position_json='{"DASHBOARD_VERSION": "2.0", "ROOT_ID": "ROOT_ID", "ROOT_ID-content": ["GRID_ID"], "GRID_ID": {"children": ["CHART_ID_1"], "id": "GRID_ID", "type": "GRID"}, "CHART_ID_1": {"children": [], "id": "CHART_ID_1", "meta": {"chartId": 123, "height": 50, "sliceName": "My New Bar Chart", "width": 12}, "type": "CHART"}}', # Simplified example
    slug='my-new-programmatic-dashboard',
    published=True
)
```

**Important Note on Dashboard `position_json` and `json_metadata`:**
These arguments are JSON strings that define the layout, chart positioning, and metadata of the dashboard. They are highly complex. The best way to get accurate `position_json` and `json_metadata` strings is to:
1.  Create a dashboard manually in the Superset UI with your desired layout and elements.
2.  Save the dashboard.
3.  Inspect the network request payload in your browser's developer tools during the save operation, or use `superset_get_resource` on the created dashboard and extract the `position_json` and `json_metadata` fields.

By combining these tools, you have powerful capabilities to manage and automate your Superset instances programmatically.