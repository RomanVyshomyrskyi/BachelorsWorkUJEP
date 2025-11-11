# SupersetMCP/tools.py
import modelcontextprotocol as mcp
import logging

logger = logging.getLogger(__name__)

# --- Placeholder Superset Client ---
# You would replace this with your real Superset API client
class MockSupersetClient:
    def __init__(self, url):
        self.url = url
        logger.info(f"Mock Superset Client connected to {url}")

    async def run_sql(self, query: str) -> dict:
        # Simulating a SQL query
        await asyncio.sleep(0.1) # Simulate network request
        if "error" in query.lower():
            return {"status": "error", "message": "SQL syntax error"}
        return {"status": "success", "columns": ["name", "value"], "rows": [["sales", 100], ["marketing", 200]]}

    async def create_dashboard(self, title: str) -> dict:
        # Simulating dashboard creation
        await asyncio.sleep(0.1)
        return {"status": "success", "dashboard_id": 123, "title": title}

# In a real app, you'd initialize this in your main() and pass it to tools
# For simplicity here, we make a global one.
# A better way is to use mcp.state - see MCP docs
client = MockSupersetClient("http://superset.example.com")
# --- End Placeholder ---


@mcp.tool()
async def run_superset_sql(sql_query: str) -> str:
    """
    Runs a SQL query against the main Superset database.
    Args:
        sql_query: The SQL query to execute.
    """
    logger.info(f"Running SQL: {sql_query}")
    result = await client.run_sql(sql_query)
    return json.dumps(result) # Return result as a JSON string


@mcp.tool()
async def create_superset_dashboard(title: str) -> str:
    """
    Creates a new, empty dashboard in Superset.
    Args:
        title: The title for the new dashboard.
    """
    logger.info(f"Creating dashboard: {title}")
    result = await client.create_dashboard(title)
    return json.dumps(result)