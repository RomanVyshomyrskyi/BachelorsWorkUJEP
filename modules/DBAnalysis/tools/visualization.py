import json
import base64
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from typing import Optional, Any
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy
from ..db_manager import DbManager
from ..strategies.base import MAX_ROWS
from modules.log_utils import LogCollector
from .data import _resolve_config, _sanitize_error


def tool_generate_chart(
    db_manager: Optional[DbManager],
    query: str,
    chart_type: str,
    x_column: str,
    y_column: str,
    title: str = "Database Analysis Chart",
    db_id: Optional[str] = None,
    db_type: Optional[str] = None,
    host: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
    dbname: Optional[str] = None,
    port: Optional[int] = None,
    max_rows: int = MAX_ROWS,
) -> Any:
    log = LogCollector(f"{__name__}.generate_chart")
    try:
        cfg = _resolve_config(db_manager, db_id, db_type, host, user, password, dbname, port)
    except ValueError as e:
        return str(e)

    if not query or not query.strip():
        return "Query cannot be empty"

    # Clamp max_rows to prevent memory exhaustion
    if max_rows > MAX_ROWS:
        max_rows = MAX_ROWS

    log.info(f"Generating {chart_type} chart from {cfg['db_type']}://{cfg['host']}:{cfg['port']}/{cfg['dbname']}")
    conn_details = ConnectionDetails(**cfg)
    strategy = get_db_strategy(cfg['db_type'], conn_details.model_dump())

    try:
        with strategy as db_context:
            log.info(f"Executing chart query: {query[:200]}")
            data = db_context.execute_query(query, max_rows=max_rows)

        if not data:
            log.warning(f"No data returned for chart from {cfg['dbname']}")
            return "No data returned from query to visualize."

        df = pd.DataFrame(data)

        if x_column not in df.columns or y_column not in df.columns:
            return f"Error: The specified columns were not found in the query result. Please verify column names."

        plt.figure(figsize=(10, 6))

        if chart_type == "bar":
            plt.bar(df[x_column].astype(str), df[y_column])
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "line":
            plt.plot(df[x_column], df[y_column], marker='o')
            plt.xticks(rotation=45, ha='right')
        elif chart_type == "scatter":
            plt.scatter(df[x_column], df[y_column])
        elif chart_type == "pie":
            plt.pie(df[y_column], labels=df[x_column].astype(str), autopct='%1.1f%%')
            plt.axis('equal')
        else:
            return f"Unsupported chart type: {chart_type}"

        plt.title(title)
        plt.xlabel(x_column)
        plt.ylabel(y_column)
        plt.tight_layout()

        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        img_bytes = buf.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        return [
            {"type": "text", "text": f"Generated {chart_type} chart"},
            {"type": "image", "data": img_base64, "mimeType": "image/png"}
        ]

    except TimeoutError as e:
        return str(e)
    except RuntimeError as e:
        return _sanitize_error(e)
    except ValueError as e:
        return str(e)
    except Exception as e:
        log.error(f"Chart generation error: {e}")
        return _sanitize_error(e)


def register_visualization_tools(mcp, db_manager=None):
    @mcp.tool(name="generate_database_chart")
    def generate_database_chart(
        query: str,
        chart_type: str,
        x_column: str,
        y_column: str,
        title: str = "Database Analysis Chart",
        db_id: Optional[str] = None,
        db_type: Optional[str] = None,
        host: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        dbname: Optional[str] = None,
        port: Optional[int] = None,
    ) -> Any:
        return tool_generate_chart(db_manager, query, chart_type, x_column, y_column, title, db_id, db_type, host, user, password, dbname, port)
