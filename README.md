
# How to run

1. From the repository root (where `docker-compose.dev.yml` lives), build and start everything:

```powershell
docker-compose -f .\docker-compose.dev.yml up --build
```

# Whrer to finde modeule documentation?
Module documentation is avalibe in `modules/*module name*/README.md`

# FastMCP Server Architecture

My `app.py` has been refactored into a **modular (plugin) architecture** using FastAPI. This design allows for easy extension of the server's functionality by simply adding new "modules" (plugins).

### How it Works

1.  **Core Server (`app.py`)**:
    *   When the application starts, it initializes a FastAPI web server.
    *   It scans the `modules` directory for any subdirectories.
    *   For each subdirectory found, it looks for a `main.py` file within it.
    *   Using Python's `importlib`, it dynamically loads this `main.py` file as a module.

2.  **Modules (`modules/*`)**:
    *   Each module's `main.py` is expected to define a FastAPI `APIRouter` instance, which **must be named `router`**.
    *   The core server then includes this `router` into the main FastAPI application.
    *   To ensure unique endpoint paths and avoid conflicts, all routes defined within a module's router are automatically prefixed with the module's folder name. For example, if a `hello_world` module has a `/hello` endpoint, it will be accessible via `/hello_world/hello`.

### How to Create a New Module

Adding new functionality (a "tool") to the FastMCP server is straightforward:

1.  **Create a Module Directory**:
    Create a new folder inside the `modules` directory. The folder name will be used as the prefix for all routes in that module.

    ```bash
    mkdir modules/your_new_module_name
    ```

2.  **Create `main.py`**:
    Inside your new module folder (`modules/your_new_module_name/`), create a `main.py` file. This file will contain your module's logic and API endpoints.

3.  **Define Your Router and Endpoints**:
    In `modules/your_new_module_name/main.py`, define your FastAPI endpoints using an `APIRouter`. **It is crucial that the `APIRouter` instance is named `router`**.

    **Example (`modules/your_new_module_name/main.py`):**
    ```python
    from fastapi import APIRouter
    from pydantic import BaseModel # Example: if your module needs data validation

    # Your module's router - MUST be named 'router'
    router = APIRouter()

    class Item(BaseModel):
        name: str
        description: str = None

    @router.get("/status", tags=["Your New Module"])
    async def get_status():
        """
        A simple endpoint to check the module's status.
        """
        return {"module": "your_new_module_name", "status": "active"}

    @router.post("/process_item", tags=["Your New Module"])
    async def process_item(item: Item):
        """
        An endpoint to process an item received by the module.
        """
        return {"message": f"Item '{item.name}' processed successfully!"}
    ```

Once you've created this structure, restart your FastMCP server. The `app.py` core will automatically discover and load `your_new_module_name`, making its endpoints accessible (e.g., `GET /your_new_module_name/status` and `POST /your_new_module_name/process_item`).

# Full Testing Environment with Docker Compose

For a complete integration testing environment, I have created a `docker-compose.yml` file that launches the FastMCP server along with instances of PostgreSQL, MariaDB, and MSSQL. This allows for end-to-end testing of modules like `DBAnalysis`.

The credentials for these databases are managed in the `.env` file for security and flexibility.