import os
import importlib.util
from fastapi import FastAPI
from fastapi.responses import JSONResponse

# --- Core Application Setup ---
app = FastAPI(
    title="FastMCP Server",
    description="A modular server that dynamically loads tools from modules.",
    version="1.0.0"
)

# --- Dynamic Module Loading ---
def load_modules(app: FastAPI):
    """
    Dynamically finds and loads modules from the 'modules' directory.
    
    A module is a directory within 'modules' that contains a 'main.py' file.
    The 'main.py' is expected to have a FastAPI APIRouter instance named 'router'.
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
                    
                    # Look for the 'router' object and register it
                    if hasattr(module, "router"):
                        # Use the module name as a prefix for all its routes
                        app.include_router(module.router, prefix=f"/{module_name}")
                        loaded_modules.append(module_name)
                        print(f"Successfully loaded module: {module_name}")
                    else:
                        print(f"Warning: Module '{module_name}' has a main.py but no 'router' object.")

                except Exception as e:
                    print(f"Error loading module '{module_name}': {e}")
    
    return loaded_modules

# --- Application Startup ---
loaded_modules = load_modules(app)

# --- Core API Endpoints ---
@app.get("/", tags=["Core"])
async def read_root():
    """
    Root endpoint that provides basic server information.
    """
    return {
        "message": "Welcome to the FastMCP Server",
        "loaded_modules": loaded_modules
    }

@app.get("/health", tags=["Core"])
async def health_check():
    """
    Health check endpoint.
    """
    return JSONResponse(content={"status": "ok"})

# To run this app for local development, use the following command:
# uvicorn app:app --reload
