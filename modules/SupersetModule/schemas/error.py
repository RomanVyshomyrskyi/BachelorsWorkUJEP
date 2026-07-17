from typing import Optional
from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    message: str
    status_code: int = 500
    tool: str = ""
    details: str = ""


class ErrorResponse(BaseModel):
    error: bool = True
    message: str
    status_code: int = 500
    tool: str = ""
    details: Optional[str] = None


class ValidationWarning(BaseModel):
    field: str
    issue: str
    severity: str = "warning"
