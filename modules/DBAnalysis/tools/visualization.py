import json
import base64
import io
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from typing import Literal, Any
from ..models.connection import ConnectionDetails
from ..strategies.factory import get_db_strategy

def tool_generate_chart(
    db_type: str,
    host: str,
    user: str,
    password: str,
    dbname: str,
    query: str,
    chart_type: str,
    x_column: str,
    y_column: str,
    title: str = "Database Analysis Chart",
    port: int = 5432
) -> Any:
    """
    Generates a chart visualization from a SQL query using Matplotlib.
    
    :param db_type: Type of database (postgres, mariadb, mssql)
    :param host: Database host address
    :param user: Database username
    :param password: Database password
    :param dbname: Database name
    :param query: SQL SELECT query to fetch data
    :param chart_type: Type of chart (bar, line, pie, scatter)
    :param x_column: Column name for the X axis (or pie labels)
    :param y_column: Column name for the Y axis (or pie values)
    :param title: Title of the chart
    :param port: Database port (default 5432)
    """
    try:
        # 1. Fetch Data
        conn_details = ConnectionDetails(
            host=host, user=user, password=password, dbname=dbname, port=port
        )
        strategy = get_db_strategy(db_type, conn_details.model_dump())
        
        with strategy as db_context:
            data = db_context.execute_query(query)
        
        if not data:
            return "No data returned from query to visualize."

        # 2. Create DataFrame
        df = pd.DataFrame(data)
        
        if x_column not in df.columns or y_column not in df.columns:
            return f"Error: Columns {x_column} or {y_column} not found in query result keys: {list(df.columns)}"

        # 3. Plotting with Matplotlib
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

        # 4. Export to Image (PNG)
        buf = io.BytesIO()
        plt.savefig(buf, format='png')
        plt.close()
        img_bytes = buf.getvalue()
        img_base64 = base64.b64encode(img_bytes).decode('utf-8')

        # 5. Return Rich Content (Image)
        return [
            {"type": "text", "text": f"Generated {chart_type} chart for query: {query}"},
            {"type": "image", "data": img_base64, "mimeType": "image/png"}
        ]

    except Exception as e:
        return f"Chart Generation Error: {str(e)}"

def register_visualization_tools(mcp):
    mcp.tool(name="generate_database_chart")(tool_generate_chart)