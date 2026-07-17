from typing import Literal
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..utils.rules_loader import get_normalization_rules
from modules.log_utils import LogCollector

def tool_get_rules() -> str:
    """
    Retrieves the current database normalization rules/standards.
    """
    return get_normalization_rules()

def tool_analyze_db(
    db_type: Literal["postgres", "mariadb", "mysql", "mssql"],
    host: str,
    user: str,
    password: str,
    dbname: str,
    port: int = 5432
) -> str:
    """
    Connects to a database, extracts its schema, and returns it alongside normalization rules.
    """
    log = LogCollector(f"{__name__}.analyze_db")
    try:
        log.info(f"Connecting to {db_type}://{host}:{port}/{dbname}")
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        
        strategy = get_db_strategy(db_type, conn_details.model_dump())

        with strategy as db_context:
            log.info("Extracting schema representation")
            schema_representation = db_context.get_schema_representation()

        rules = get_normalization_rules()
        log.info(f"Schema extracted successfully from {dbname}")

        result = f"""
ANALYSIS DATA RETRIEVED SUCCESSFULLY.

--- NORMALIZATION RULES ---
{rules}

--- DATABASE SCHEMA ({db_type}) ---
{schema_representation}

--- INSTRUCTIONS FOR AI ---
Please analyze the schema above based on the normalization rules provided.
"""
        return result

    except Exception as e:
        msg = f"Error analyzing {db_type} database {dbname}: {e}"
        log.error(msg)
        return f"Error: {e}"

def register_analysis_tools(mcp):
    mcp.tool(name="get_normalization_rules")(tool_get_rules)
    mcp.tool(name="analyze_database_schema")(tool_analyze_db)