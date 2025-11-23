# modules/DBAnalysis/main.py

import os
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field
from typing import Literal

from .strategies import get_db_strategy

# The router instance MUST be named 'router'
router = APIRouter()

# --- Pydantic Models for API Data Validation ---

class ConnectionDetails(BaseModel):
    """Defines the structure for database connection details."""
    host: str = Field(..., example="localhost")
    user: str = Field(..., example="admin")
    password: str
    dbname: str = Field(..., example="mydatabase")
    port: int | None = Field(None, example=5432)

class AnalysisRequest(BaseModel):
    """Defines the request body for the analysis endpoint."""
    db_type: Literal["postgres", "mariadb", "mssql"]
    connection_details: ConnectionDetails

# --- Helper Function to Load Rules ---

def get_normalization_rules() -> str:
    """Loads the normalization rules from the markdown file."""
    rules_path = os.path.join(os.path.dirname(__file__), "normalization_rules.md")
    try:
        with open(rules_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: Normalization rules file not found."

# --- API Endpoint ---

@router.post("/analyze", tags=["Database Analysis"])
async def analyze_database(request: AnalysisRequest = Body(...)):
    """
    Analyzes a database's schema for normalization and suggests improvements.
    
    This endpoint uses the Strategy pattern to connect to a database,
    extract its schema, and then (conceptually) uses an LLM with a set of
    normalization rules to provide suggestions.
    
    **Note:** This implementation uses placeholder logic and does not
    make a real database connection.
    """
    try:
        # 1. Select the appropriate strategy based on the request
        strategy = get_db_strategy(request.db_type, request.connection_details.dict())

        # 2. Use the strategy to connect and get the schema
        # The 'with' statement ensures connect() and disconnect() are called.
        with strategy as db_context:
            schema_representation = db_context.get_schema_representation()

        # 3. Load the normalization rules
        rules = get_normalization_rules()

        # 4. (Conceptual) Prepare a prompt for an LLM and get suggestions
        # In a real application, you would send the schema and rules to an LLM API.
        llm_prompt = f"""
        Here is a set of database normalization rules:
        ---
        {rules}
        ---
        
        Here is the schema of a database:
        ---
        {schema_representation}
        ---
        
        Based on the rules provided, please analyze this database schema for potential
        violations of 1NF, 2NF, and 3NF. For each violation you find,
        describe the issue and suggest a specific, corrected schema structure.
        """

        # 5. Return a simulated response
        return {
            "status": "analysis_complete",
            "db_type": request.db_type,
            "suggestions": "This is a placeholder response. In a real implementation, this field would contain AI-generated suggestions for improving your database normalization.",
            "llm_prompt_for_debugging": llm_prompt
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ConnectionError as e:
        raise HTTPException(status_code=503, detail=f"Database connection failed: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")

@router.get("/rules", tags=["Database Analysis"])
async def get_rules():
    """
    Retrieves the content of the normalization rules file.
    """
    return {"rules": get_normalization_rules()}
