from pydantic import BaseModel, Field

class ConnectionDetails(BaseModel):
    host: str = Field(..., description="Database host, e.g., localhost")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    dbname: str = Field(..., description="Database name")
    port: int | None = Field(None, description="Database port, e.g., 5432")
