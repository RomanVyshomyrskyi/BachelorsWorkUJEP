"""
Superset batch insert tool - Insert data into tables via SQL Lab.

Provides tool_superset_batch_insert_rows - inserts data rows into a table
by building INSERT statements and executing them via Superset SQL Lab.
"""

import asyncio
import json
import logging
from typing import Optional

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.sql_lab.execute import sqllab_execute_query
from modules.log_utils import LogCollector

log = LogCollector(__name__)


def _escape_sql_value(value) -> str:
    """Escape a value for SQL INSERT statement."""
    if value is None or value == '' or value == 'null' or value == 'undefined':
        return 'NULL'
    if isinstance(value, bool):
        return 'TRUE' if value else 'FALSE'
    if isinstance(value, (int, float)):
        return str(value)
    # String - escape single quotes
    s = str(value).replace("'", "''")
    return f"'{s}'"


def _build_insert_sql(table_name: str, columns: list[str], rows: list[list]) -> str:
    """Build INSERT statement for multiple rows."""
    col_str = ', '.join(columns)
    val_groups = []
    for row_values in rows:
        val_str = ', '.join(_escape_sql_value(v) for v in row_values)
        val_groups.append(f'({val_str})')
    return f"INSERT INTO {table_name} ({col_str}) VALUES\n" + ',\n'.join(val_groups)


async def tool_superset_batch_insert_rows(
    manager: ConnectionManager,
    server_id: str,
    database_id: int,
    table_name: str,
    columns: list[str],
    data_rows: list[dict],
    batch_size: int = 50,
    schema: Optional[str] = None,
) -> str:
    """
    Insert rows into a Superset-connected database table via SQL Lab.

    Converts data rows to INSERT statements and executes them via Superset
    SQL Lab in batches.

    Args:
        manager: The ConnectionManager instance with Superset connection details.
        server_id: The ID of the configured Superset server.
        database_id: The numeric ID of the database to insert into.
        table_name: Target table name.
        columns: List of column names.
        data_rows: List of row objects (each object is a row with column->value mappings).
        batch_size: Number of rows per INSERT batch (default: 50, max: 200).
        schema: Optional schema name (PostgreSQL).

    Returns:
        JSON string with success, total_rows, inserted_rows, failed_rows, batches, errors.
    """
    if not columns:
        return json.dumps({
            'success': False, 'error': 'No columns specified', 'status_code': 400
        })
    if not data_rows:
        return json.dumps({
            'success': False, 'error': 'No rows to insert', 'status_code': 400
        })

    # Convert data_rows (objects) to flat arrays in column order
    rows = []
    for row_obj in data_rows:
        row_values = [row_obj.get(col, '') for col in columns]
        rows.append(row_values)

    total_rows = len(rows)
    inserted = 0
    failed = 0
    errors = []
    batches = []

    for i in range(0, total_rows, batch_size):
        batch = rows[i:i + batch_size]
        batch_num = (i // batch_size) + 1

        try:
            sql = _build_insert_sql(table_name, columns, batch)
            result = await sqllab_execute_query(
                manager, server_id, database_id, sql, schema=schema
            )
            result_data = json.loads(result)

            # Check if query was successful
            if result_data.get('status') == 'success' or 'data' in result_data:
                inserted += len(batch)
                batches.append({
                    'batch_number': batch_num,
                    'start_row': i + 1,
                    'end_row': min(i + batch_size, total_rows),
                    'rows': len(batch),
                    'success': True,
                    'error': None,
                })
            else:
                failed += len(batch)
                error_msg = result_data.get('error', result_data.get('result', {}).get('error', 'Unknown error'))
                errors.append(f'Batch {batch_num}: {error_msg}')
                batches.append({
                    'batch_number': batch_num,
                    'start_row': i + 1,
                    'end_row': min(i + batch_size, total_rows),
                    'rows': len(batch),
                    'success': False,
                    'error': error_msg,
                })
        except Exception as e:
            failed += len(batch)
            error_msg = str(e)
            errors.append(f'Batch {batch_num}: {error_msg}')
            batches.append({
                'batch_number': batch_num,
                'start_row': i + 1,
                'end_row': min(i + batch_size, total_rows),
                'rows': len(batch),
                'success': False,
                'error': error_msg,
            })

    return json.dumps({
        'success': inserted > 0,
        'total_rows': total_rows,
        'inserted_rows': inserted,
        'failed_rows': failed,
        'batches': batches,
        'errors': errors if errors else None,
    })
