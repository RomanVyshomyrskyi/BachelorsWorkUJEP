"""
Error formatting utilities for Superset chart validation.

Provides format_error_summary() and format_validation_error() for
converting validation errors into human-readable output.
"""

from typing import Any, Dict, List, Optional


def format_error_summary(errors: List[str]) -> str:
    """Format validation errors into a readable numbered list.

    Args:
        errors: List of error message strings from validate_chart_params.

    Returns:
        A human-readable summary string, or a success message if no errors.

        Example:
            >>> errors = ["Missing metric field", "Invalid groupby format"]
            >>> print(format_error_summary(errors))
            Found 2 error(s):
              1. Missing metric field
              2. Invalid groupby format
            >>> format_error_summary([])
            'No errors found. Parameters are valid.'
    """
    if not errors:
        return "No errors found. Parameters are valid."

    lines = [f"Found {len(errors)} error(s):"]
    for i, err in enumerate(errors, 1):
        lines.append(f"  {i}. {err}")
    return "\n".join(lines)


def format_validation_error(
    viz_type: str,
    params: Dict[str, Any],
    errors: List[str],
    fixes_applied: Optional[List[str]] = None,
) -> str:
    """Format a complete validation result with viz_type, params summary, and errors.

    Args:
        viz_type: The Superset viz_type string.
        params: Chart params that were validated.
        errors: List of error messages from validation.
        fixes_applied: Optional list of fix descriptions applied by auto_fix.

    Returns:
        A human-readable string with full validation context.
    """
    lines: List[str] = []
    lines.append(f"--- Chart Validation: {viz_type} ---")
    lines.append(f"Params keys: {list(params.keys())}")
    lines.append("")

    if not errors:
        lines.append("Status: VALID")
    else:
        lines.append(f"Status: {len(errors)} error(s) found")
        lines.append("")
        lines.append(format_error_summary(errors))

    if fixes_applied:
        lines.append("")
        lines.append(f"Fixes applied ({len(fixes_applied)}):")
        for i, fix in enumerate(fixes_applied, 1):
            lines.append(f"  {i}. {fix}")

    return "\n".join(lines)
