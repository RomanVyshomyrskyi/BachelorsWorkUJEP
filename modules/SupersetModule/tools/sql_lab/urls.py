"""SQL Lab URL generation for Superset MCP integration.

Provides open_sql_lab_with_context() - generates URLs that open
Superset's SQL Lab interface with database and SQL pre-selected.
"""

from typing import Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.exceptions import SqlLabError
from modules.SupersetModule.schemas.sqllab import SqlLabUrlResponse


async def open_sql_lab_with_context(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    sql: Optional[str] = None,
    schema: Optional[str] = None
) -> str:
    """
    MCP Tool: superset_open_sql_lab_with_context - Open SQL Lab UI with pre-filled SQL.

    Generates a URL that opens Superset's SQL Lab interface with the database and
    optional SQL query pre-selected/filled. Useful for redirecting users to SQL
    Lab with a specific query ready to execute.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to open SQL Lab for.
        sql: Optional SQL query string to pre-fill in the SQL Lab editor.
        schema: Optional schema name to pre-select in the SQL Lab interface.

    Returns:
        JSON string containing the SQL Lab URL, database_id, sql (if provided),
        and schema (if provided). Returns SqlLabError JSON if the server is not found.

    Examples:
        result = await open_sql_lab_with_context(
            manager, server_id="main", database_id=1,
            sql="SELECT * FROM public.sales", schema="public"
        )
        # Returns JSON with a URL that opens SQL Lab pre-filled with the query
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return SqlLabError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        base_url = ctx.config.base_url.rstrip("/")

        params = f"dbId={database_id}"
        if sql:
            params += f"&qtSQL={sql}"
        if schema:
            params += f"&schema={schema}"

        sql_lab_url = f"{base_url}/sqllab/?{params}"

        return SqlLabUrlResponse(
            url=sql_lab_url,
            database_id=database_id,
            sql=sql,
            schema=schema,
        ).model_dump_json(indent=2)
    except Exception as e:
        return SqlLabError(f"Unexpected error generating SQL Lab URL: {e}", details=str(e)).to_json()
