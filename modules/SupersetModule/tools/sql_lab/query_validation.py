"""
SQL query validation for Superset MCP tools.

Provides validation functions to enforce strict query type restrictions
for Superset SQL Lab operations. DELETE is always FORBIDDEN across all tools.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Operations that are ALWAYS FORBIDDEN (across all Superset tools)
ALWAYS_FORBIDDEN = frozenset([
    'DELETE',
    'DROP',
    'TRUNCATE',
])

# Operations forbidden in SELECT queries (blocks all DDL and DML)
SELECT_FORBIDDEN = frozenset([
    'INSERT',
    'UPDATE',
    'DELETE',
    'DROP',
    'TRUNCATE',
    'CREATE',
    'ALTER',
    'REPLACE',
    'MERGE',
    'GRANT',
    'REVOKE',
    'EXEC',
    'EXECUTE',
])

# Operations forbidden in INSERT queries
INSERT_FORBIDDEN = frozenset([
    'DELETE',
    'UPDATE',
    'DROP',
    'TRUNCATE',
    'CREATE',
    'ALTER',
    'SELECT',
])

# Operations forbidden in UPDATE queries
UPDATE_FORBIDDEN = frozenset([
    'DELETE',
    'INSERT',
    'DROP',
    'TRUNCATE',
    'CREATE',
    'ALTER',
    'SELECT',
])


def _get_first_keyword(query: str) -> Optional[str]:
    """
    Extract the first significant SQL keyword from a query.

    Strips comments and whitespace, then returns the first word that
    matches a SQL statement keyword.

    Args:
        query: Raw SQL query string.

    Returns:
        First keyword string (e.g., 'SELECT', 'INSERT', 'UPDATE') or None.
    """
    cleaned = query.strip()

    # Remove SQL comments
    cleaned = re.sub(r'--.*$', '', cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r'/\*.*?\*/', '', cleaned, flags=re.DOTALL)
    cleaned = cleaned.strip()

    if not cleaned:
        return None

    first_word = cleaned.split()[0].upper()
    return first_word


def _check_forbidden(query: str, forbidden: frozenset, tool_name: str) -> str:
    """
    Check if a query contains any forbidden keywords.

    Scans the query text (case-insensitive) for forbidden operation keywords.
    Also checks for forbidden keywords hidden in table/column names.

    Args:
        query: Raw SQL query string.
        forbidden: Set of forbidden uppercase keywords.
        tool_name: Name of the tool (for error messages).

    Returns:
        Cleaned query string if no forbidden keywords found.

    Raises:
        ValueError: If any forbidden keyword is found.
    """
    upper = query.upper()

    for keyword in forbidden:
        if keyword in upper:
            raise ValueError(
                f"Security violation: {tool_name} - '{keyword}' is FORBIDDEN. "
                f"This tool does not allow {keyword} operations."
            )

    logger.info(f"Query validation passed for {tool_name} ({len(query)} chars)")
    return query


def validate_select_query(query: str) -> str:
    """
    Validate that a query is a SELECT-type statement only.

    Allows: SELECT, WITH (CTE), SHOW, DESCRIBE, EXPLAIN
    Forbids: INSERT, UPDATE, DELETE, DROP, TRUNCATE, CREATE, ALTER, and all other DDL/DML

    Args:
        query: Raw SQL query string.

    Returns:
        The validated query string.

    Raises:
        ValueError: If the query is not a SELECT-type statement or contains forbidden operations.
    """
    if not query or not query.strip():
        raise ValueError("Security violation: superset_execute_sql_query - Empty query")

    first_keyword = _get_first_keyword(query)

    allowed = {'SELECT', 'WITH', 'SHOW', 'DESCRIBE', 'EXPLAIN', 'SET', 'USE'}
    if first_keyword not in allowed:
        raise ValueError(
            f"Security violation: superset_execute_sql_query - Only SELECT/WITH/SHOW/DESCRIBE queries allowed. "
            f"Detected operation: '{first_keyword}'"
        )

    return _check_forbidden(query, SELECT_FORBIDDEN, 'superset_execute_sql_query')


def validate_insert_query(query: str) -> str:
    """
    Validate that a query is an INSERT statement only.

    Allows: INSERT, REPLACE INTO
    Forbids: DELETE, UPDATE, INSERT INTO SELECT, DROP, TRUNCATE, CREATE, ALTER, SELECT

    Args:
        query: Raw SQL query string.

    Returns:
        The validated query string.

    Raises:
        ValueError: If the query is not an INSERT statement or contains forbidden operations.
    """
    if not query or not query.strip():
        raise ValueError("Security violation: superset_execute_sql_insert - Empty query")

    first_keyword = _get_first_keyword(query)

    allowed = {'INSERT', 'REPLACE'}
    if first_keyword not in allowed:
        raise ValueError(
            f"Security violation: superset_execute_sql_insert - Only INSERT statements allowed. "
            f"Detected operation: '{first_keyword}'"
        )

    return _check_forbidden(query, INSERT_FORBIDDEN, 'superset_execute_sql_insert')


def validate_update_query(query: str) -> str:
    """
    Validate that a query is an UPDATE statement only.

    Allows: UPDATE
    Forbids: DELETE, INSERT, DROP, TRUNCATE, CREATE, ALTER, SELECT

    Args:
        query: Raw SQL query string.

    Returns:
        The validated query string.

    Raises:
        ValueError: If the query is not an UPDATE statement or contains forbidden operations.
    """
    if not query or not query.strip():
        raise ValueError("Security violation: superset_execute_sql_update - Empty query")

    first_keyword = _get_first_keyword(query)

    if first_keyword != 'UPDATE':
        raise ValueError(
            f"Security violation: superset_execute_sql_update - Only UPDATE statements allowed. "
            f"Detected operation: '{first_keyword}'"
        )

    return _check_forbidden(query, UPDATE_FORBIDDEN, 'superset_execute_sql_update')


def validate_dml_query(query: str, tool_name: str) -> str:
    """
    Universal DML validation - ALWAYS FORBID DELETE.

    This is a safety layer that runs before any DML query to ensure
    DELETE is never allowed, regardless of the tool.

    Args:
        query: Raw SQL query string.
        tool_name: Name of the calling tool (for error messages).

    Returns:
        The validated query string.

    Raises:
        ValueError: If DELETE is found in the query.
    """
    if not query or not query.strip():
        raise ValueError(f"Security violation: {tool_name} - Empty query")

    return _check_forbidden(query, ALWAYS_FORBIDDEN, tool_name)
