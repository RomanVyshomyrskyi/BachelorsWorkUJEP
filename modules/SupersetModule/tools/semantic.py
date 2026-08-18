"""
Semantic analysis tools for Apache Superset MCP integration.

Provides tools for analyzing database tables at a semantic level: profiling
table statistics, suggesting metrics and dimensions for charting, and
generating data dictionaries with column metadata.

MCP Tools Provided:
    - superset_profile_table: Profile a database table for statistics
    - superset_suggest_metrics: Auto-suggest metrics for numeric columns
    - superset_suggest_dimensions: Auto-suggest dimension columns for grouping
    - superset_get_data_dictionary: Generate a data dictionary for a table
"""

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.semantic_layer import (
    profile_table as _profile_table,
    suggest_metrics as _suggest_metrics,
    suggest_dimensions as _suggest_dimensions,
    get_data_dictionary as _get_data_dictionary,
)


async def profile_table(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    MCP Tool: superset_profile_table - Profile a database table for statistics.

    Analyzes a database table and returns comprehensive statistics including
    row count, column types, null percentages, min/max/avg values, standard
    deviation, and top frequent values for each column. Useful for understanding
    data distribution before building charts.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database containing the table.
        schema: The schema name containing the table (e.g., 'public', 'dbo').
        table: The name of the table to profile.

    Returns:
        JSON string containing table profiling results: row count, per-column
        statistics (nulls, distinct count, min, max, avg, stddev, top values),
        and overall table metadata.

    Examples:
        result = await profile_table(manager, server_id="main", database_id=1, schema="public", table="sales")
        # Returns JSON with row count, per-column stats (nulls, min, max, top values), and table metadata
    """
    # Delegate to the semantic layer implementation for table profiling logic
    return await _profile_table(manager, server_id, database_id, schema, table)


async def suggest_metrics(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    MCP Tool: superset_suggest_metrics - Auto-suggest metrics for numeric columns.

    Analyzes the numeric columns in a table and suggests appropriate metric
    aggregations (SUM, AVG, COUNT, MIN, MAX) for each. Useful for quickly
    identifying which columns can be used as chart metrics.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database containing the table.
        schema: The schema name containing the table.
        table: The name of the table to analyze.

    Returns:
        JSON string containing suggested metrics for each numeric column,
        including recommended aggregation functions (SUM, AVG, COUNT, MIN, MAX).

    Examples:
        result = await suggest_metrics(manager, server_id="main", database_id=1, schema="public", table="sales")
        # Returns JSON with per-column metric suggestions (SUM for amount, AVG for price, COUNT for id)
    """
    # Delegate to the semantic layer implementation for metric suggestion logic
    return await _suggest_metrics(manager, server_id, database_id, schema, table)


async def suggest_dimensions(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    """
    MCP Tool: superset_suggest_dimensions - Auto-suggest dimension columns for grouping.

    Identifies text, categorical, date, and boolean columns that are suitable
    for use as grouping dimensions (groupby) or filtering fields in charts.
    Useful for discovering which columns work well as chart dimensions.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database containing the table.
        schema: The schema name containing the table.
        table: The name of the table to analyze.

    Returns:
        JSON string containing suggested dimension columns with their types
        (text, categorical, date, boolean) and suitability for grouping/filtering.

    Examples:
        result = await suggest_dimensions(manager, server_id="main", database_id=1, schema="public", table="sales")
        # Returns JSON with dimension suggestions (product_name as text, sale_date as date, region as categorical)
    """
    # Delegate to the semantic layer implementation for dimension suggestion logic
    return await _suggest_dimensions(manager, server_id, database_id, schema, table)


async def get_data_dictionary(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
    include_statistics: bool = True,
) -> str:
    """
    MCP Tool: superset_get_data_dictionary - Generate a data dictionary for a table.

    Generates a comprehensive data dictionary for a database table, including
    column names, data types, recommended chart roles (dimension/metric), and
    optional statistics (null percentages, top values, etc.). Useful for
    documenting table structure and understanding column usage.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database containing the table.
        schema: The schema name containing the table.
        table: The name of the table to generate the dictionary for.
        include_statistics: Whether to include column statistics (nulls, top values,
            min/max/avg). Defaults to True. Set to False for faster response.

    Returns:
        JSON string containing the data dictionary with column names, types,
        recommended roles, and optionally statistics for each column.

    Examples:
        result = await get_data_dictionary(
            manager, server_id="main", database_id=1, schema="public",
            table="sales", include_statistics=True
        )
        # Returns JSON with column names, types, chart roles, and column statistics
    """
    # Delegate to the semantic layer implementation for data dictionary generation
    return await _get_data_dictionary(
        manager, server_id, database_id, schema, table, include_statistics
    )
