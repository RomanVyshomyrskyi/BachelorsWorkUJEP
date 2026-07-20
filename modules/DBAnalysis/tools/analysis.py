from typing import Optional
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..utils.rules_loader import get_normalization_rules
from ..db_manager import DbManager
from modules.log_utils import LogCollector
from .data import _resolve_config, _sanitize_error


def tool_get_rules() -> str:
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
    log = LogCollector(f"{__name__}.analyze_db")
    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)

    log.info(f"Connecting to {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}")
    conn_details = ConnectionDetails(**cfg)
    strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

    try:
        with strategy as db_context:
            log.info("Extracting schema representation")
            schema_representation = db_context.get_schema_representation()

        rules = get_normalization_rules()
        log.info(f"Schema extracted successfully from {cfg['dbname']}")

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
        return str(e)
    except RuntimeError as e:
        return _sanitize_error(e)
    except Exception as e:
        log.error(f"Error analyzing database: {e}")
        return _sanitize_error(e)


def register_analysis_tools(mcp, db_manager=None):
    mcp.tool(name="get_normalization_rules")(tool_get_rules)

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
        return tool_analyze_db(db_manager, db_id, db_type, host, user, password, dbname, port)
