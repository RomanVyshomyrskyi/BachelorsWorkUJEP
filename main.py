import os
import sys
import importlib.util
from fastmcp import FastMCP

# --- Core Application Setup ---
# Примітка: dependencies у конструкторі можуть викликати DeprecationWarning,
# але це не критично. Краще керувати залежностями через requirements.txt.
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
                    # Import the module's main.py
                    spec = importlib.util.spec_from_file_location(f"modules.{module_name}.main", main_file_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # --- KEY CHANGE HERE ---
                    if hasattr(module, "register") and callable(module.register):
                        module.register(mcp_server)
                        loaded_modules.append(module_name)
                        # ВАЖЛИВО: file=sys.stderr (щоб не ламати MCP протокол)
                        print(f"Successfully loaded module: {module_name}", file=sys.stderr)
                    else:
                        print(f"Warning: Module '{module_name}' has no 'register(mcp)' function.", file=sys.stderr)

                except Exception as e:
                    print(f"Error loading module '{module_name}': {e}", file=sys.stderr)
    
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
def health_check() -> str:
    """
    Returns the health status of the server.
    """
    return "OK"

# --- Entry Point ---
if __name__ == "__main__":
    mcp.run()