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
    return await _profile_table(manager, server_id, database_id, schema, table)


async def suggest_metrics(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    return await _suggest_metrics(manager, server_id, database_id, schema, table)


async def suggest_dimensions(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
) -> str:
    return await _suggest_dimensions(manager, server_id, database_id, schema, table)


async def get_data_dictionary(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    schema: str,
    table: str,
    include_statistics: bool = True,
) -> str:
    return await _get_data_dictionary(
        manager, server_id, database_id, schema, table, include_statistics
    )
