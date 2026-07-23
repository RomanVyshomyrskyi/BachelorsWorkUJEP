"""Custom exception classes for Superset MCP tool operations.

This module defines a hierarchy of domain-specific exceptions that provide
structured error information including HTTP status codes, tool context, and
additional details. All exceptions inherit from SupersetToolError which provides
a to_json() method for serialization.
"""


class SupersetToolError(Exception):
    """Base exception for all Superset tool operation errors.

    Provides structured error information including a human-readable message,
    HTTP status code for API responses, the tool name where the error occurred,
    and additional context-specific details.
    """

    def __init__(self, message: str, status_code: int = 500, tool: str = "", details: str = ""):
        """Initialize the base SupersetToolError with structured error metadata.

        Args:
            message: Human-readable description of the error that occurred.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            tool: Name of the Superset MCP tool where the error originated.
                Used for tracing and error categorization.
            details: Additional context-specific error details that supplement
                the main message. Can contain stack traces, parameter values, etc.
        """
        # Store individual error fields as attributes for structured access
        self.message = message
        self.status_code = status_code
        self.tool = tool
        self.details = details
        # Initialize parent Exception class with the error message
        super().__init__(self.message)

    def to_json(self) -> str:
        """Serialize the error to a JSON string for structured error reporting.

        Returns:
            JSON-formatted string containing error, message, status_code, tool,
            and details fields. Pretty-printed with 2-space indentation.
        """
        import json
        # Build the JSON structure with all error metadata fields
        return json.dumps({
            "error": True,
            "message": self.message,
            "status_code": self.status_code,
            "tool": self.tool,
            "details": self.details,
        }, indent=2)


class ChartError(SupersetToolError):
    """Exception raised when a chart-related operation fails.

    Automatically sets tool context to "chart" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a chart-specific error.

        Args:
            message: Human-readable description of the chart error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the chart error.
        """
        # Chain to parent with tool pre-set to "chart"
        super().__init__(message=message, status_code=status_code, tool="chart", details=details)


class DashboardError(SupersetToolError):
    """Exception raised when a dashboard-related operation fails.

    Automatically sets tool context to "dashboard" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a dashboard-specific error.

        Args:
            message: Human-readable description of the dashboard error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the dashboard error.
        """
        # Chain to parent with tool pre-set to "dashboard"
        super().__init__(message=message, status_code=status_code, tool="dashboard", details=details)


class DatasetError(SupersetToolError):
    """Exception raised when a dataset-related operation fails.

    Automatically sets tool context to "dataset" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a dataset-specific error.

        Args:
            message: Human-readable description of the dataset error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the dataset error.
        """
        # Chain to parent with tool pre-set to "dataset"
        super().__init__(message=message, status_code=status_code, tool="dataset", details=details)


class DatabaseError(SupersetToolError):
    """Exception raised when a database-related operation fails.

    Automatically sets tool context to "database" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a database-specific error.

        Args:
            message: Human-readable description of the database error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the database error.
        """
        # Chain to parent with tool pre-set to "database"
        super().__init__(message=message, status_code=status_code, tool="database", details=details)


class SqlLabError(SupersetToolError):
    """Exception raised when a SQL Lab query operation fails.

    Automatically sets tool context to "sqllab" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a SQL Lab-specific error.

        Args:
            message: Human-readable description of the SQL Lab error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the SQL Lab error.
        """
        # Chain to parent with tool pre-set to "sqllab"
        super().__init__(message=message, status_code=status_code, tool="sqllab", details=details)


class ExploreError(SupersetToolError):
    """Exception raised when an Explore (chart builder) operation fails.

    Automatically sets tool context to "explore" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize an Explore-specific error.

        Args:
            message: Human-readable description of the Explore error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the Explore error.
        """
        # Chain to parent with tool pre-set to "explore"
        super().__init__(message=message, status_code=status_code, tool="explore", details=details)


class ServerError(SupersetToolError):
    """Exception raised when a server-level operation fails.

    Automatically sets tool context to "server" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a server-specific error.

        Args:
            message: Human-readable description of the server error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the server error.
        """
        # Chain to parent with tool pre-set to "server"
        super().__init__(message=message, status_code=status_code, tool="server", details=details)


class TransferError(SupersetToolError):
    """Exception raised when a dashboard transfer operation fails.

    Automatically sets tool context to "transfer" for error categorization.
    """

    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        """Initialize a transfer-specific error.

        Args:
            message: Human-readable description of the transfer error.
            status_code: HTTP status code associated with the error.
                Defaults to 500 (Internal Server Error).
            details: Additional context-specific details about the transfer error.
        """
        # Chain to parent with tool pre-set to "transfer"
        super().__init__(message=message, status_code=status_code, tool="transfer", details=details)
