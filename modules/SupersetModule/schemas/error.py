"""
Pydantic schemas for Superset MCP tool error handling and validation.

Defines models for structured error responses and validation warnings
used across all Superset API interactions for consistent error reporting.
"""

from typing import Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """
    Structured error information from a Superset MCP tool operation.

    Used to return detailed error context including the originating tool,
    HTTP status code, and human-readable message with additional details.
    """
    message: str  # Human-readable error description
    status_code: int = 500  # HTTP status code associated with the error (default: 500)
    tool: str = ""  # Name of the MCP tool that generated the error
    details: str = ""  # Additional technical details or stack context


class ErrorResponse(BaseModel):
    """
    Standard error response model for all Superset API failures.

    Used as the unified error format returned by tool functions when
    an API call fails. Contains a boolean error flag, message, and status.
    """
    error: bool = True  # Always True to indicate this is an error response
    message: str  # Human-readable error description
    status_code: int = 500  # HTTP status code (default: 500)
    tool: str = ""  # Name of the tool that produced the error
    details: Optional[str] = None  # Additional context (optional for brief errors)


class ValidationWarning(BaseModel):
    """
    Non-blocking warning about potential issues in input data.

    Used to flag fields that passed validation but may cause problems
    at runtime (e.g., deprecated values, unusual configurations).
    """
    field: str  # The field name that has a potential issue
    issue: str  # Description of the warning
    severity: str = "warning"  # Warning severity level (default: "warning")
