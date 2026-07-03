import os
import sys
import importlib.util
import logging
from fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
import uvicorn
# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# --- Core Application Setup ---
mcp = FastMCP("FastMCP Server")

# --- Dynamic Module Loading ---
def load_modules(mcp_server: FastMCP):
    """
    Dynamically finds and loads modules from the 'modules' directory.
    """
    modules_dir = "modules"
    loaded_modules = []
    
    if not os.path.exists(modules_dir):
        return loaded_modules

    for module_name in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, module_name)
        if os.path.isdir(module_path):
            main_file_path = os.path.join(module_path, "main.py")
            if os.path.isfile(main_file_path):
                try:
                    # Import the module's main.py using its full package name
                    module_pkg = f"modules.{module_name}.main"
                    module = importlib.import_module(module_pkg)
                    
                    if hasattr(module, "register") and callable(module.register):
                        module.register(mcp_server)
                        loaded_modules.append(module_name)
                        logging.info(f"Successfully loaded module: {module_name}")
                    else:
                        logging.warning(f"Module '{module_name}' has no 'register(mcp)' function.")

                except Exception as e:
                    logging.error(f"Error loading module '{module_name}': {e}", exc_info=True)
    
    return loaded_modules

# --- Application Startup ---
loaded_modules = load_modules(mcp)

# --- Core Tools ---
@mcp.tool()
def list_loaded_modules() -> dict:
    """
    Returns a list of all dynamically loaded modules.
    """
    return {
        "message": "Welcome to the FastMCP Server",
        "loaded_modules": loaded_modules
    }

@mcp.tool()
def list_available_tools() -> list:
    """
    Returns a list of all available tools across all modules.
    """
    tools = []
    for name, tool in mcp._tool_manager._tools.items():
        tools.append({
            "name": name,
            "description": tool.description,
            "module": tool.fn.__module__
        })
    return tools

@mcp.tool()
def health_check() -> str:
    """
    Returns the health status of the server.
    """
    return "OK"

# --- FastAPI Integration for Documentation ---
app = FastAPI(
    title="FastMCP Server",
    description="Auto-generated documentation for FastMCP tools",
    version="1.0.0"
)

# Enable CORS to allow Open Web UI to connect
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Force OpenAPI 3.0.0 for compatibility and strip 422 errors
from fastapi.openapi.utils import get_openapi
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        servers=[{"url": "/"}]
    )
    openapi_schema["openapi"] = "3.0.0"
    
    # Remove 422 validation errors which clutter the spec and confuse some parsers
    for path, methods in openapi_schema.get("paths", {}).items():
        for method, details in methods.items():
            if "responses" in details and "422" in details["responses"]:
                del details["responses"]["422"]
                
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# Tools that only read data and should be GET in Swagger (NOT exhaustive - add as needed)
READ_ONLY_TOOLS = {
    "list_superset_servers", "list_loaded_modules", "list_available_tools",
    "health_check", "superset_server_status", "superset_available_resource_types",
    "superset_list_resources", "list_dashboards", "superset_get_resource",
    "superset_get_chart_api_info", "superset_sqllab_get_query_results",
    "superset_get_database_schema", "superset_get_dashboard_api_info",
    "superset_get_standard_chart_params", "superset_get_chart_creation_rules",
    "superset_get_dashboard_creation_rules",
    "get_mermaid_file_descriptions", "get_mermaid_doc_content",
    "generate_all_mermaid_diagrams",
    "analyze_database_schema", "get_normalization_rules", "get_table_data",
    "run_read_only_sql",
}

# 1. Register all MCP tools as FastAPI endpoints to generate Swagger docs
for tool_name, tool in mcp._tool_manager._tools.items():
    try:
        # Use tool.fn directly
        endpoint = tool.fn
        
        # Determine the tag based on the module name
        # If the tool is from a module, it will be in modules.<module_name>...
        module_path = tool.fn.__module__
        if module_path.startswith("modules."):
            tag = module_path.split(".")[1]
        else:
            tag = "Core"
        
        methods = ["GET"] if tool_name in READ_ONLY_TOOLS else ["POST"]
            
        app.add_api_route(
            path=f"/{tool_name}",
            endpoint=endpoint,
            methods=methods,
            tags=[tag],
            summary=tool.description or f"Execute {tool_name}",
            name=tool_name,
            operation_id=tool_name
        )
        logging.info(f"Registered FastAPI route for tool: {tool_name} [{', '.join(methods)}] with tag: {tag}")
    except Exception as e:
        logging.error(f"Failed to register route for tool '{tool_name}': {e}")

# 2. Mount the FastMCP app (Starlette) to handle the actual MCP protocol (SSE)
try:
    mcp_app = mcp.http_app(transport="sse")
    app.mount("/mcp", mcp_app)
    logging.info("Mounted FastMCP SSE server at /mcp")
except Exception as e:
    logging.error(f"Failed to mount FastMCP app: {e}")

# 3. Add redirects for the default paths to maintain compatibility
@app.get("/sse")
async def handle_sse_redirect():
    return RedirectResponse(url="/mcp/sse")

@app.get("/messages")
async def handle_messages_redirect():
    return RedirectResponse(url="/mcp/messages")

# --- Entry Point ---
if __name__ == "__main__":
    logging.info("Starting FastMCP Server with FastAPI integration...")
    logging.info("Documentation available at: http://localhost:8000/docs")
    logging.info("MCP SSE Endpoint at: http://localhost:8000/mcp/sse")
    
    # Run FastAPI app with Uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
