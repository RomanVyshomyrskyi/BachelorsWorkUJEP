import os
import sys
import json
import io
import base64
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Literal, List, Dict, Any

# Імпорти для візуалізації
import matplotlib.pyplot as plt
import pandas as pd

# Налаштування matplotlib для роботи без дисплея (headless server)
plt.switch_backend('Agg')

# Імпортуємо вашу існуючу логіку стратегій
from .strategies import get_db_strategy

# --- Pydantic Models ---

class ConnectionDetails(BaseModel):
    host: str = Field(..., description="Database host, e.g., localhost")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    dbname: str = Field(..., description="Database name")
    port: int | None = Field(None, description="Database port, e.g., 5432")

# --- Helper Functions ---

def get_normalization_rules() -> str:
    """Loads the normalization rules from the markdown file."""
    rules_path = os.path.join(os.path.dirname(__file__), "normalization_rules.md")
    try:
        with open(rules_path, "r") as f:
            return f.read()
    except FileNotFoundError:
        return "Error: Normalization rules file not found."

# --- MCP Registration ---

def register(mcp: FastMCP):
    """
    Реєструє інструменти цього модуля у головному сервері.
    """

    @mcp.tool(name="get_normalization_rules")
    def tool_get_rules() -> str:
        """
        Retrieves the current database normalization rules/standards.
        """
        return get_normalization_rules()

    @mcp.tool(name="analyze_database_schema")
    def tool_analyze_db(
        db_type: Literal["postgres", "mariadb", "mssql"],
        host: str,
        user: str,
        password: str,
        dbname: str,
        port: int = 5432
    ) -> str:
        """
        Connects to a database, extracts its schema, and returns it alongside normalization rules.
        """
        try:
            conn_details = ConnectionDetails(
                host=host, user=user, password=password, dbname=dbname, port=port
            )
            
            strategy = get_db_strategy(db_type, conn_details.dict())

            with strategy as db_context:
                schema_representation = db_context.get_schema_representation()

            rules = get_normalization_rules()

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
            return f"Error: {e}"

    @mcp.tool(name="run_read_only_sql")
    def tool_run_sql(
        db_type: Literal["postgres", "mariadb", "mssql"],
        host: str,
        user: str,
        password: str,
        dbname: str,
        query: str,
        port: int = 5432
    ) -> str:
        """
        Executes a read-only SQL query (SELECT) against the database.
        Returns data in JSON format, which the AI can format into a Markdown table.
        """
        try:
            conn_details = ConnectionDetails(
                host=host, user=user, password=password, dbname=dbname, port=port
            )
            
            strategy = get_db_strategy(db_type, conn_details.dict())

            with strategy as db_context:
                results = db_context.execute_query(query)

            return json.dumps(results, default=str)

        except Exception as e:
            return f"Query Execution Error: {e}"

    @mcp.tool(name="generate_database_chart")
    def tool_generate_chart(
        db_type: Literal["postgres", "mariadb", "mssql"],
        host: str,
        user: str,
        password: str,
        dbname: str,
        query: str,
        chart_type: Literal["bar", "line", "pie", "scatter"],
        x_column: str,
        y_column: str,
        title: str = "Database Analysis Chart",
        port: int = 5432
    ) -> Any:
        """
        Generates a chart visualization from a SQL query.
        
        ARGS:
        - query: SQL query to fetch data (e.g. "SELECT category, count(*) as cnt FROM products GROUP BY category")
        - chart_type: Type of chart to generate
        - x_column: Column name for X axis (categories/time)
        - y_column: Column name for Y axis (values)
        """
        try:
            # 1. Fetch Data
            conn_details = ConnectionDetails(
                host=host, user=user, password=password, dbname=dbname, port=port
            )
            strategy = get_db_strategy(db_type, conn_details.dict())
            
            with strategy as db_context:
                data = db_context.execute_query(query)
            
            if not data:
                return "No data returned from query to visualize."

            # 2. Create DataFrame
            df = pd.DataFrame(data)
            
            if x_column not in df.columns or y_column not in df.columns:
                return f"Error: Columns {x_column} or {y_column} not found in query result keys: {list(df.columns)}"

            # 3. Plotting
            plt.figure(figsize=(10, 6))
            
            if chart_type == "bar":
                plt.bar(df[x_column], df[y_column], color='skyblue')
            elif chart_type == "line":
                plt.plot(df[x_column], df[y_column], marker='o', linestyle='-', color='green')
            elif chart_type == "scatter":
                plt.scatter(df[x_column], df[y_column], color='red')
            elif chart_type == "pie":
                plt.pie(df[y_column], labels=df[x_column], autopct='%1.1f%%')
            
            plt.title(title)
            plt.xlabel(x_column)
            plt.ylabel(y_column)
            plt.xticks(rotation=45)
            plt.tight_layout()

            # 4. Save to Buffer & Encode
            buf = io.BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            img_base64 = base64.b64encode(buf.read()).decode('utf-8')
            plt.close()

            # 5. Return Rich Content (Image)
            # Gemini CLI expects a specific structure for images
            return [
                {"type": "text", "text": f"Generated {chart_type} chart for query: {query}"},
                {"type": "image", "data": img_base64, "mimeType": "image/png"}
            ]

        except Exception as e:
            return f"Chart Generation Error: {e}"