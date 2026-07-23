"""
Analysis Tools - Database schema analysis and normalization rules MCP tools.

Provides MCP tools for retrieving normalization rules and analyzing
database schemas. The analyze_database_schema tool connects to a database,
extracts its schema representation (tables, columns, relationships), and
returns it along with normalization rules for AI-powered schema review.
"""

from typing import Optional
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..utils.rules_loader import get_normalization_rules
from ..db_manager import DbManager
from modules.log_utils import LogCollector
from .data import _resolve_config, _sanitize_error


def tool_get_rules() -> str:
    """
    MCP tool for retrieving the normalization rules reference document.

    Returns the contents of the normalization_rules.md file which contains
    guidelines for database schema normalization that the AI can use
    when evaluating database designs.

    Returns:
        The full text content of the normalization rules markdown file,
        or an error message if the file is not found.
    """
    # Load and return the normalization rules from the markdown file
    return get_normalization_rules()


def tool_analyze_db(
    db_manager: Optional[DbManager],
    db_id: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """
    MCP tool for analyzing a database schema and returning normalization context.

    This tool connects to a database using the provided configuration,
    extracts the full schema representation (tables, columns, data types,
    nullability, primary keys, foreign key relationships), and returns it
    along with the normalization rules for AI-assisted schema analysis.

    Args:
        db_manager: Optional DbManager instance for looking up configurations by ID.
        db_id: Optional database ID to look up in the configuration file.
        db_type: Database type (postgres, mariadb, mysql, mssql).
        host: Database host address (used if db_id is not provided).
        user: Database username (used if db_id is not provided).
        password: Database password (used if db_id is not provided).
        dbname: Database name (used if db_id is not provided).
        port: Database port (used if db_id is not provided).

    Returns:
        A formatted string containing:
        - A success header.
        - The normalization rules reference.
        - The database schema representation (tables, columns, relationships).
        - Instructions for the AI to analyze the schema against the rules.

    Description:
        1. Resolves database configuration from db_id or individual fields.
        2. Creates a ConnectionDetails object and gets the appropriate strategy.
        3. Opens a database context manager (connect -> extract schema -> disconnect).
        4. Loads the normalization rules reference document.
        5. Returns a formatted report with schema data and AI instructions.

    Raises:
        TimeoutError: If the schema extraction takes too long.
        RuntimeError: If a database-level error occurs during extraction.
    """
    # Initialize the log collector for tracking tool operations
    log = LogCollector(f"{__name__}.analyze_db")

    try:
        # Resolve the database configuration (from db_id lookup or individual fields)
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)

    except ValueError as e:
        # Return validation errors directly to the caller
        return str(e)

    # Log the connection details for the analysis operation
    log.info(f"Connecting to {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}")

    # Create a ConnectionDetails Pydantic model from the resolved configuration
    conn_details = ConnectionDetails(**cfg)

    # Get the appropriate database strategy based on the resolved db_type
    strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

    try:
        # Open a database context manager: connects, extracts schema, then disconnects
        with strategy as db_context:
            # Extract the full schema representation (tables, columns, relationships)
            log.info("Extracting schema representation")
            schema_representation = db_context.get_schema_representation()

        # Load the normalization rules reference document for AI context
        rules = get_normalization_rules()

        # Log successful schema extraction
        log.info(f"Schema extracted successfully from {cfg['dbname']}")

        # Return a formatted report containing rules, schema, and AI instructions
        return f"""
ANALYSIS DATA RETRIEVED SUCCESSFULLY.

--- NORMALIZATION RULES ---
{rules}

--- DATABASE SCHEMA ({cfg['db_type']}) ---
{schema_representation}

--- INSTRUCTIONS FOR AI ---
Please analyze the schema above based on the normalization rules provided.
"""

    except TimeoutError as e:
        # Return timeout errors directly to the caller with context
        return str(e)
    except RuntimeError as e:
        # Sanitize internal runtime errors before returning to the caller
        return _sanitize_error(e)
    except Exception as e:
        # Catch any other unexpected errors, log them, and return a sanitized message
        log.error(f"Error analyzing database: {e}")
        return _sanitize_error(e)


def register_analysis_tools(mcp, db_manager=None):
    """
    Register analysis-related MCP tools with the FastMCP server.

    Description:
        Maps the tool_get_rules and tool_analyze_db functions to their
        respective MCP tool names. The analyze_database_schema tool is
        registered as a nested function that passes the db_manager.

    Args:
        mcp: The FastMCP server instance to register tools on.
        db_manager: Optional DbManager instance for configuration lookup.
    """
    # Register the normalization rules retrieval tool
    mcp.tool(name="get_normalization_rules")(tool_get_rules)

    # Register the database schema analysis tool with db_manager context
    @mcp.tool(name="analyze_database_schema")
    def analyze_database_schema(
        db_id: Optional[str] = None,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        port: Optional[int] = None,
    ) -> str:
        """MCP tool wrapper that calls tool_analyze_db with the db_manager context."""
        return tool_analyze_db(db_manager, db_id, db_type, host, user, password, dbname, port)
