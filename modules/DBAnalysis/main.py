import os
from fastmcp import FastMCP
from pydantic import BaseModel, Field
from typing import Literal

# Імпортуємо вашу існуючу логіку стратегій
# (Припускаємо, що файл strategies.py знаходиться поруч)
from .strategies import get_db_strategy

# --- Pydantic Models (Залишаємо для валідації всередині логіки) ---

class ConnectionDetails(BaseModel):
    host: str = Field(..., description="Database host, e.g., localhost")
    user: str = Field(..., description="Database user")
    password: str = Field(..., description="Database password")
    dbname: str = Field(..., description="Database name")
    port: int | None = Field(None, description="Database port, e.g., 5432")

# --- Helper Functions ---

def get_normalization_rules() -> str:
    """Loads the normalization rules from the markdown file."""
    # Використовуємо абсолютний шлях відносно поточного файлу
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
        Use this to understand what rules to apply when analyzing a schema.
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
        
        ARGS:
        - db_type: Type of database (postgres, mariadb, mssql)
        - host: Host address
        - user: Username
        - password: Password
        - dbname: Name of the database
        - port: Port number (default 5432)
        """
        
        # 1. Формуємо об'єкт connection_details (як було в оригіналі)
        # Ми "розгорнули" аргументи у функції, щоб LLM було легше їх заповнювати,
        # але всередині збираємо їх назад у модель.
        try:
            conn_details = ConnectionDetails(
                host=host, user=user, password=password, dbname=dbname, port=port
            )
            
            # 2. Отримуємо стратегію
            strategy = get_db_strategy(db_type, conn_details.dict())

            # 3. Виконуємо підключення та отримуємо схему
            with strategy as db_context:
                schema_representation = db_context.get_schema_representation()

            # 4. Отримуємо правила
            rules = get_normalization_rules()

            # 5. ПОВЕРТАЄМО КОНТЕКСТ (Схема + Правила)
            # На відміну від API, тут ми не повертаємо "placeholder".
            # Ми повертаємо сирі дані, щоб Клод (або інша модель) міг зробити аналіз.
            result = f"""
ANALYSIS DATA RETRIEVED SUCCESSFULLY.

--- NORMALIZATION RULES ---
{rules}

--- DATABASE SCHEMA ({db_type}) ---
{schema_representation}

--- INSTRUCTIONS FOR AI ---
Please analyze the schema above based on the normalization rules provided.
Identify violations of 1NF, 2NF, and 3NF. Suggest specific SQL corrections.
            """
            return result

        except ValueError as e:
            return f"Validation Error: {str(e)}"
        except ConnectionError as e:
            return f"Database Connection Failed: {e}"
        except Exception as e:
            return f"Unexpected Error: {e}"