# Development Docker setup — simulate two networks

This repository contains `docker-compose.dev.yml`, a Compose configuration that simulates two isolated networks:

- prod_net — "production" simulation with MSSQL, MariaDB, MongoDB, a SQLite file, and a Superset instance built from the local `./Superset` repo.
- dev_net — a separate network with the same DB types and another Superset instance built from the same local repo (useful for comparing local/dev vs production-like environments).

Files added

- `docker-compose.dev.yml` — Compose file that builds Superset from `./Superset` and creates the DB services for both networks.

How it works (quick)

- Each network has services named with `_prod` or `_dev` suffixes. The Superset services are built from the local `./Superset` folder (they use the repository's `Dockerfile`).
- SQLite is represented by a tiny container that creates the DB file in a named volume; the superset containers mount the same named volume so they can use that file as the metadata DB.
- Ports are mapped on the host so both Superset instances can run simultaneously:
  - Production-like Superset: http://localhost:8088
  - Development Superset: http://localhost:8089

Default credentials and connection notes

- MSSQL (both): SA password set to `Your_strong_P@ssw0rd!` — change this before using in any real environment.
- MariaDB prod: root password `rootpass`; MariaDB dev: root password `devroot`.
- MongoDB no authentication in this compose (for dev/test only).

Connection examples (from Superset UI when adding new database connections):

- MariaDB (prod): mysql+pymysql://root:rootpass@mariadb_prod:3306/demo
- MariaDB (dev): mysql+pymysql://root:devroot@mariadb_dev:3306/demo
- MSSQL: mssql+pyodbc://sa:Your_strong_P@ssw0rd!@mssql_prod:1433/<YOUR_DB>?driver=ODBC+Driver+17+for+SQL+Server
  - Note: ODBC drivers may need to be available in the Superset image or use pymssql connector.
- MongoDB: mongodb://mongo_prod:27017
- SQLite metadata DB (already pointed to by the Superset containers): sqlite:////var/lib/superset/prod_superset.db or sqlite:////var/lib/superset/dev_superset.db

How to run

1. From the repository root (where `docker-compose.dev.yml` lives), build and start everything:

```powershell
docker-compose -f .\docker-compose.dev.yml up --build
```

2. Wait for images to build and services to warm up. Open the Dev Superset at http://localhost:8089 and the Prod-like Superset at http://localhost:8088.

Notes, assumptions, and limitations

- This is intended for local development only. The images and passwords are not production-secure.
- The Superset image is built from the `./Superset` directory in this workspace and uses the repo's `Dockerfile`. The repo's Dockerfile may expect additional build args or setup steps; if you run into build errors, consult the repo's `Dockerfile` and `INSTALL.md` in `./Superset` for prerequisites.
- MSSQL official images are large and may require platform compatibility and sufficient resources. If you do not need MSSQL locally, consider removing or replacing it with a lightweight substitute.
- Superset often requires initialization steps (e.g., `superset db upgrade`, `superset init`). If the image's entrypoint does not run these automatically, you can exec into the container and run them, or extend the Dockerfile to run them at startup.

Next steps (optional suggestions)

- Add an entrypoint script for `superset_dev` that runs `superset db upgrade` and `superset init` on first start.
- Add seeded sample data and example connections (SQLAlchemy URIs) as environment variables so Superset registers the example datasources automatically.
- If you want to use Postgres instead of SQLite for Superset metadata, add a Postgres service and point `SUPERSET_SQLALCHEMY_CONN` to it.

If you'd like, I can:

- Add an init script for Superset to auto-run migrations and create an admin user.
- Add example SQLAlchemy URIs and a small seed script that registers the DBs in Superset automatically.

---

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

### Running the Server Locally (for Development)

Even though the primary deployment is via Docker, you can easily run and test your server locally using `uvicorn`:

1.  **Install Dependencies**: Ensure you have `fastapi` installed.

    ```bash
    pip install -r requirements.txt
    ```

2.  **Start the Server**:

    ```bash
    uvicorn app:app --reload
    ```
    The `--reload` flag is convenient for development as it automatically restarts the server when you make code changes.

Access the interactive API documentation at `http://127.0.0.1:8000/docs` to see all loaded modules and their endpoints.