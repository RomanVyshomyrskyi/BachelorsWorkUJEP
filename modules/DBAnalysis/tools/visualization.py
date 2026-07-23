"""
Visualization Tools - Chart generation from SQL query results.

Provides MCP tools for generating data visualizations (bar, line, pie, scatter)
from database query results using Matplotlib. Queries are executed against
the specified database and the resulting data is rendered as PNG images
encoded in base64 format for display in MCP clients.
"""

import json
import base64
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend for server-side rendering
import matplotlib.pyplot as plt
from typing import Literal, Any
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from modules.log_utils import LogCollector
import time
from modules.metrics import get_metrics


def _default_port(db_type: str) -> int:
    """
    Return the default port for a given database type.

    Args:
        db_type: The database type string (e.g., "postgres", "mariadb", "mysql", "mssql").

    Returns:
        The default port number as an integer.
    """
    return {"postgres": 5432, "mariadb": 3306, "mysql": 3306, "mssql": 1433}.get(db_type, 5432)


def tool_generate_chart(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    query: str,
    chart_type: str,
    x_column: str,
    y_column: str,
    title: str = "Database Analysis Chart",
    port: int = 0
) -> Any:
    """
    MCP tool for generating a chart visualization from a SQL query result.

    This tool connects to a database, executes a SELECT query, retrieves the
    result set, and renders it as a Matplotlib chart. The chart is returned
    as a list containing a text description and a base64-encoded PNG image.

    Description:
        1. Resolves the default port if not explicitly provided.
        2. Establishes a database connection using the appropriate strategy.
        3. Executes the provided SELECT query via the database context manager.
        4. Converts the result set to a Pandas DataFrame.
        5. Validates that the requested x and y columns exist in the results.
        6. Creates a Matplotlib figure of the specified chart type (bar, line, pie, scatter).
        7. Renders the chart to a PNG image buffer and encodes it as base64.
        8. Returns a list with a text description and the base64 image data.

    Args:
        db_type: Type of database to connect to (postgres, mariadb, mysql, mssql).
        host: Database server hostname or IP address.
        user: Database username for authentication.
        password: Database password for authentication.
        dbname: Name of the database to query.
        query: SQL SELECT query to fetch the data for the chart.
        chart_type: Type of chart to generate (bar, line, pie, scatter).
        x_column: Column name for the X axis (or pie labels for pie charts).
        y_column: Column name for the Y axis (or pie values for pie charts).
        title: Title displayed on the chart (default: "Database Analysis Chart").
        port: Database port number (0 = use default for db_type).

    Returns:
        A list of content items containing:
        - A text item with the query summary.
        - An image item with the base64-encoded PNG chart.
        Or a string error message if the operation fails.
    """
    # Initialize the log collector for tracking tool operations
    log = LogCollector(f"{__name__}.generate_chart")

    # Resolve the default port if not explicitly provided (port=0 means use default)
    if not port:
        port = _default_port(db_type)

    try:
        # Log the chart generation request with database connection details
        log.info(f"Generating {chart_type} chart from {db_type}://{host}:{port}/{dbname}")

        # Create a ConnectionDetails Pydantic model to hold connection parameters
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )

        # Get the appropriate database strategy based on db_type and connection details
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        # Open a database context manager: connects, executes query, then disconnects
        with strategy as db_context:
            # Log and execute the SELECT query to fetch data for the chart
            log.info(f"Executing chart query: {query[:200]}")
            data = db_context.execute_query(query)

        # Check if the query returned any data; if not, return an error message
        if not data:
            log.warning(f"No data returned for chart from {dbname}")
            return "No data returned from query to visualize."

        # Convert the list-of-dicts result set into a Pandas DataFrame for plotting
        df = pd.DataFrame(data)

        # Validate that both the x and y columns exist in the query results
        if x_column not in df.columns or y_column not in df.columns:
            return f"Error: Columns {x_column} or {y_column} not found in query result keys: {list(df.columns)}"

        # Create a new Matplotlib figure with a standard size for the chart
        plt.figure(figsize=(10, 6))

        # Generate the appropriate chart type based on user selection
        if chart_type == "bar":
            # Bar chart: x-axis labels from x_column, y-axis values from y_column
            plt.bar(df[x_column].astype(str), df[y_column])
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "line":
            # Line chart: connects data points with lines, marks them with circles
            plt.plot(df[x_column], df[y_column], marker='o')
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "scatter":
            # Scatter plot: plots individual x/y coordinate pairs
            plt.scatter(df[x_column], df[y_column])
        elif chart_type == "pie":
            # Pie chart: slices based on y_column values, labeled by x_column
            plt.pie(df[y_column], labels=df[x_column].astype(str), autopct='%1.1f%%')
            plt.axis('equal')
        else:
            # Reject unsupported chart types with an error message
            return f"Unsupported chart type: {chart_type}"

        # Set the chart title and axis labels for clarity
        plt.title(title)
        plt.xlabel(x_column)
        plt.ylabel(y_column)
        # Adjust layout to prevent label clipping
        plt.tight_layout()

        # Render the chart to an in-memory PNG image buffer
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()  # Close the figure to free memory
        img_bytes = buf.getvalue()  # Extract the raw PNG bytes

        # Encode the PNG image bytes as a base64 string for JSON transport
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        # Return the chart as structured content: text description + base64 image
        return [
            {"type": "text", "text": f"Generated {chart_type} chart for query: {query}"},
            {"type": "image", "data": img_base64, "mimeType": "image/png"}
        ]

    except Exception as e:
        # Catch any unexpected errors and return a user-friendly error message
        return f"Chart Generation Error: {str(e)}"


def register_visualization_tools(mcp, db_manager=None):
    """
    Register visualization-related MCP tools with the FastMCP server.

    Description:
        Maps the tool_generate_chart function to the MCP tool name
        "generate_database_chart" so it can be invoked by MCP clients.

    Args:
        mcp: The FastMCP server instance to register tools on.
        db_manager: Optional DbManager instance (not used by visualization tools).
    """
    # Register the chart generation function as an MCP tool
    mcp.tool(name="generate_database_chart")(tool_generate_chart)
