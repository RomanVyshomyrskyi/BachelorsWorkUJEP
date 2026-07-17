class SupersetToolError(Exception):
    def __init__(self, message: str, status_code: int = 500, tool: str = "", details: str = ""):
        self.message = message
        self.status_code = status_code
        self.tool = tool
        self.details = details
        super().__init__(self.message)

    def to_json(self) -> str:
        import json
        return json.dumps({
            "error": True,
            "message": self.message,
            "status_code": self.status_code,
            "tool": self.tool,
            "details": self.details,
        }, indent=2)


class ChartError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="chart", details=details)


class DashboardError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="dashboard", details=details)


class DatasetError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="dataset", details=details)


class DatabaseError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="database", details=details)


class SqlLabError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="sqllab", details=details)


class ExploreError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="explore", details=details)


class ServerError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="server", details=details)


class TransferError(SupersetToolError):
    def __init__(self, message: str, status_code: int = 500, details: str = ""):
        super().__init__(message=message, status_code=status_code, tool="transfer", details=details)
