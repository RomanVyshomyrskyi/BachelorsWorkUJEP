import os
import sys
import inspect
import importlib.util
import logging
from fastmcp import FastMCP
from fastapi import FastAPI
from fastapi.responses import RedirectResponse, Response
 import uvicorn
 from modules.registry import ModuleRegistry, resolve_dependency_order
 from modules.metrics import get_metrics

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Core Application Setup ---
mcp = FastMCP("FastMCP Server")
module_registry = ModuleRegistry()

# --- Dynamic Module Loading ---

def _read_module_metadata(module_name: str) -> dict:
    module_dir = os.path.join("modules", module_name)
    main_file = os.path.join(module_dir, "main.py")
    metadata = {"depends_on": [], "name": module_name}

    if not os.path.isfile(main_file):
        return metadata

    with open(main_file, "r") as f:
        source = f.read()

    import ast
    try:
        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "depends_on":
                        if isinstance(node.value, ast.List):
                            metadata["depends_on"] = [
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant)
                            ]
    except SyntaxError:
        pass

    return metadata


def load_modules(mcp_server: FastMCP) -> list:
    modules_dir = "modules"
    loaded_modules = []

    if not os.path.exists(modules_dir):
        return loaded_modules

    module_metas = {}
    for module_name in os.listdir(modules_dir):
        module_path = os.path.join(modules_dir, module_name)
        if os.path.isdir(module_path):
            main_file_path = os.path.join(module_path, "main.py")
            if os.path.isfile(main_file_path):
                meta = _read_module_metadata(module_name)
                module_metas[module_name] = meta

    dep_map = {name: meta["depends_on"] for name, meta in module_metas.items()}
    try:
        load_order = resolve_dependency_order(dep_map)
        logger.info(f"Module load order (resolved dependencies): {load_order}")
    except ValueError as e:
        logger.error(f"Dependency resolution failed: {e}")
        return loaded_modules

    for module_name in load_order:
        main_file_path = os.path.join(modules_dir, module_name, "main.py")
        try:
            module_pkg = f"modules.{module_name}.main"
            module = importlib.import_module(module_pkg)

            if hasattr(module, "register") and callable(module.register):
                sig = inspect.signature(module.register)
                if "registry" in sig.parameters:
                    module.register(mcp_server, registry=module_registry)
                else:
                    module.register(mcp_server)

                loaded_modules.append(module_name)
                deps = module_metas[module_name]["depends_on"]
                logger.info(f"Loaded module: {module_name} (depends_on: {deps})")
            else:
                logger.warning(f"Module '{module_name}' has no 'register(mcp)' function.")

        except Exception as e:
            logger.error(f"Error loading module '{module_name}': {e}", exc_info=True)

    return loaded_modules


# --- Application Startup ---
loaded_modules = load_modules(mcp)

# --- Core Tools ---
@mcp.tool()
def list_loaded_modules() -> dict:
    return {"message": "Modules loaded", "loaded_modules": loaded_modules}

@mcp.tool()
def list_available_tools() -> list:
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
    return "OK"

# --- FastAPI Integration for Documentation ---
app = FastAPI(
    title="FastMCP Server",
    description="Auto-generated documentation for FastMCP tools",
    version="1.1.0"
)

# Enable CORS for trusted origins only
from fastapi.middleware.cors import CORSMiddleware
import os

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST"],
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
    "superset_list_resources", "list_dashboards", "list_charts", "list_databases",
    "list_datasets", "superset_get_resource", "get_chart_info", "get_dashboard_info",
    "get_database_info", "get_dataset_info", "superset_get_chart_api_info",
    "superset_sqllab_get_query_results", "superset_get_database_schema",
    "superset_get_dashboard_api_info", "superset_get_standard_chart_params",
    "superset_get_chart_creation_rules", "superset_get_dashboard_creation_rules",
    "get_schema", "get_instance_info", "get_chart_preview", "get_chart_data",
    "get_chart_type_schema",
    "get_mermaid_doc_content", "get_mermaid_file_descriptions",
    "generate_all_mermaid_diagrams",
    "analyze_database_schema", "get_normalization_rules", "get_table_data",
    "run_read_only_sql",
}

# 1. Register all MCP tools as FastAPI endpoints to generate Swagger docs
for tool_name, tool in mcp._tool_manager._tools.items():
    try:
        endpoint = tool.fn

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

# 4. Add observability endpoints
 @app.get("/metrics")
 async def prometheus_metrics():
from modules.metrics import get_metrics
 from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
     mc = get_metrics()
     return Response(content=str(generate_latest()), media_type=CONTENT_TYPE_LATEST)

 @app.get("/errors")
 async def get_recent_errors():
     mc = get_metrics()
     return mc.get_errors()

# --- Entry Point ---
if __name__ == "__main__":
    logging.info("Starting FastMCP Server with FastAPI integration...")
    logging.info("Documentation available at: http://localhost:8000/docs")
    logging.info("MCP SSE Endpoint at: http://localhost:8000/mcp/sse")

    uvicorn.run(app, host="0.0.0.0", port=8000)
