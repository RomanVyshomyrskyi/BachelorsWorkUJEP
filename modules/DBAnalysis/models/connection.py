from pydantic import BaseModel, Field, field_validator

class ConnectionDetails(BaseModel):
    host: str = Field(..., description="Database host, e.g., localhost", min_length=1)
    user: str = Field(..., description="Database user", min_length=1)
    password: str = Field(..., description="Database password", min_length=1)
    dbname: str = Field(..., description="Database name", min_length=1)
    port: int | None = Field(None, description="Database port, e.g., 5432")
