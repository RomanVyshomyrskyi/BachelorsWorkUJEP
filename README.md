# AutomationMCP Superset

A modular **Model Context Protocol (MCP)** server that provides AI agents with tools to manage Apache Superset instances — creating, editing, transferring, and analyzing dashboards, charts, datasets, and databases. Built with **FastMCP**, **FastAPI**, and a **plugin-based module architecture** with cross-module dependency resolution.

The project also includes a **React/TypeScript frontend** for visual dashboard export/import management, and an **observability stack** (Prometheus + Grafana) for monitoring.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FastMCP + FastAPI                        │
│  (main.py — bootstraps modules, mounts SSE/HTTP, Swagger)    │
├─────────────────────────────────────────────────────────────┤
│                     ModuleRegistry                           │
│  (dependency resolution via Kahn's topological sort)         │
├──────────┬──────────────┬──────────────────┬────────────────┤
│Superset  │  DBAnalysis  │ StatisticalMethods│   mermaid      │
│ Module   │   Module     │     Module        │    Module      │
│ (50+     │  (DB schema  │  (Regression &    │  (Diagram      │
│  tools)  │   analysis)  │   ML tools)       │   generation)  │
└──────────┴──────────────┴──────────────────┴────────────────┘
         │            │            │               │
         └────────────┴────────────┴───────────────┘
                          │
              ┌───────────┴───────────┐
              │   External Services    │
              │  PostgreSQL / MariaDB  │
              │  MSSQL / Superset API  │
              └───────────────────────┘
```

### How It Works

1. **`main.py`** boots the FastMCP server and scans the `modules/` directory for subdirectories containing `main.py`.
2. It reads each module's `depends_on` list via **AST parsing** (no import needed).
3. A **topological sort** (Kahn's algorithm) resolves the correct load order so dependencies are always loaded first.
4. Each module's `register(mcp, registry)` function is called, registering MCP tools and exposing its public API.
5. Every registered tool is also exposed as a **FastAPI route** for Swagger/OpenAPI documentation.
6. Two MCP transports are mounted: **Streamable HTTP** (`/mcp`) and **SSE** (`/sse`).

---

## Project Structure

```
AutomationMCPSuperset/
├── main.py                      # Bootstrapper: module loading, FastAPI, MCP mounts
├── docker-compose.yml           # Full stack: MCP server, DBs, Grafana, Prometheus, frontend
├── .env                         # Database credentials, CORS settings
├── Dockerfile                   # Server container definition
│
├── modules/                     # Plugin modules (each is a self-contained package)
│   ├── registry.py              # ModuleRegistry + Kahn's topological sort
│   ├── metrics.py               # Prometheus metrics collector
│   ├── log_utils.py             # Structured logging utilities
│   ├── openapi_utils.py         # Docstring → OpenAPI schema conversion
│   │
│   ├── SupersetModule/          # Core Superset management (50+ tools)
│   │   ├── main.py              # Entry point: depends_on, register(), get_module_api()
│   │   ├── tools/               # Tool implementations by domain
│   │   │   ├── server/          # Server listing, status, configs
│   │   │   ├── charts/          # Chart CRUD, generation, schemas
│   │   │   ├── dashboards/      # Dashboard CRUD, layouts, linking
│   │   │   ├── datasets/        # Dataset creation, schema discovery
│   │   │   ├── databases/       # Database info, connections
│   │   │   ├── sqllab/          # SQL execution, saved queries
│   │   │   ├── transfer/        # Cross-server dashboard transfer
│   │   │   ├── validation/      # Chart/dashboard validation & fixing
│   │   │   ├── semantic/        # Data profiling, dictionaries, metrics
│   │   │   └── ...              # More tool groups
│   │   ├── schemas/             # Pydantic models for API responses
│   │   ├── chart_strategies/    # Chart-type-specific parameter builders
│   │   └── ...
│   │
│   ├── DBAnalysis/              # Database analysis & profiling
│   │   ├── main.py
│   │   ├── strategies/          # Per-DB strategies (PostgreSQL, MariaDB, MSSQL)
│   │   ├── tools/               # Analysis, data extraction, visualization
│   │   └── models/              # Connection models
│   │
│   ├── StatisticalMethods/      # Regression & ML tools
│   │   ├── main.py
│   │   └── regression/          # Linear, polynomial, logistic, SVM, tree/forest
│   │
│   └── mermaid/                 # Mermaid diagram generation
│       ├── main.py
│       └── ...
│
├── frontend/                    # React/TypeScript web UI
│   ├── src/
│   │   ├── api/service.ts       # Backend API client
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # DashboardPage, SettingsPage
│   │   ├── types/               # TypeScript interfaces
│   │   └── styles/              # Global CSS
│   ├── vite.config.ts           # Vite config with API proxy rules
│   └── Dockerfile               # Nginx-based production build
│
├── docs/                        # Sphinx documentation
│   ├── index.rst
│   ├── modules.rst              # Python API reference
│   └── frontend.rst             # Frontend API reference
│
├── monitoring/                  # Observability stack
│   ├── prometheus/              # Prometheus config
│   └── grafana/                 # Grafana dashboard provisioning
│
└── tests/                       # pytest test suite
    └── modules/                 # Per-module tests
```

---

## Module System

### Module Lifecycle

```
1. Discovery          2. Dependency Resolution     3. Loading
┌──────────────┐      ┌──────────────────────┐     ┌──────────────────┐
│ Scan modules/ │ ──→ │ Parse depends_on via  │ ──→ │ import_module()  │
│ for main.py   │      │ AST (no import)      │      │ register(mcp,    │
│               │      │ Kahn's topo sort     │      │   registry)     │
└──────────────┘      └──────────────────────┘     └──────────────────┘
```

### How Modules Call Each Other

Modules declare dependencies in `main.py` via a top-level `depends_on` list. The loader ensures dependencies are loaded **before** the modules that depend on them.

At runtime, a module accesses another module's API through the shared `ModuleRegistry`:

```python
# In modules/YourModule/main.py
depends_on = ["DBAnalysis", "SupersetModule"]

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    if registry is not None:
        # Access DBAnalysis API
        db_api = registry.get_module_api("DBAnalysis")
        if db_api:
            strategy = db_api["get_db_strategy"]("postgresql", conn_details)
            schema = strategy.extract_schema()

        # Access SupersetModule API
        superset_api = registry.get_module_api("SupersetModule")
        if superset_api:
            manager = superset_api["ConnectionManager"](module_dir)
```

**Key rules:**
- Dependencies are declared via `depends_on` list in `main.py` (parsed via AST, no import needed)
- The loader performs **topological sorting** — dependencies load first
- **Circular dependencies** raise a `ValueError` at startup
- **Missing dependencies** do not block loading — the module receives `None` from `get_module_api()` and must handle it
- APIs are registered via `registry.register_module_api("ModuleName", get_module_api())`

### Current Modules

| Module | depends_on | Key Exposed API |
|---|---|---|
| `SupersetModule` | (none) | `ConnectionManager`, `api_request`, `execute_request` |
| `DBAnalysis` | (none) | `get_db_strategy`, `get_normalization_rules` |
| `StatisticalMethods` | (none) | All regression functions |
| `mermaid` | (none) | `get_mermaid_doc_content`, `get_mermaid_file_descriptions` |

---

## How to Start

### Prerequisites

- **Docker** and **Docker Compose**
- **Python 3.10+** (for local development without Docker)
- **Node.js 18+** (for local frontend development)

### Option 1: Docker Compose (Recommended)

Start the full stack (MCP server + databases + Grafana + Prometheus + frontend):

```bash
docker-compose up --build
```

This launches:
| Service | Port | Description |
|---|---|---|
| FastMCP Server | `8000` | MCP endpoints + Swagger docs (`/docs`) |
| Frontend | `8081` | React web UI for dashboard management |
| PostgreSQL | `5432` | Test database |
| MariaDB | `3306` | Test database |
| MSSQL | `1433` | Test database |
| Grafana | `3000` | Dashboards (admin/admin) |
| Prometheus | `9090` | Metrics scraper |

### Option 2: Local Development (Backend Only)

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8000"

# Start the server
python main.py
```

Server will be available at:
- **Swagger docs**: http://localhost:8000/docs
- **MCP Streamable HTTP**: http://localhost:8000/mcp
- **MCP SSE**: http://localhost:8000/sse/sse
- **Metrics**: http://localhost:8000/metrics
- **Recent errors**: http://localhost:8000/errors

### Option 3: Local Frontend Development

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at `http://localhost:3000` and proxies API requests to the backend at `http://host.docker.internal:8000`.

---

## Creating a New Module

### Step 1: Create the Directory Structure

```bash
mkdir -p modules/MyModule/tools
touch modules/MyModule/__init__.py
touch modules/MyModule/main.py
touch modules/MyModule/tools/__init__.py
```

### Step 2: Write `main.py`

```python
"""MyModule — short description of what this module does."""
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

# ── Dependencies ──────────────────────────────────────────────
# List the folder names of modules this module depends on.
# The loader will ensure they are loaded BEFORE this module.
depends_on = ["SupersetModule"]  # empty list [] if no dependencies

# ── Public API ────────────────────────────────────────────────
# These functions/classes will be accessible to other modules
# via registry.get_module_api("MyModule")
def get_module_api():
    return {
        "my_function": my_function,
        "MyClass": MyClass,
    }

# ── Registration ──────────────────────────────────────────────
def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    """Register MCP tools and expose the module API."""

    # 1. Register MCP tools
    @mcp.tool(name="my_tool")
    async def my_tool(server_id: str, param: str) -> str:
        """Description of what this tool does — shown in Swagger and to the LLM.

        Args:
            server_id: The Superset server ID.
            param: Some parameter description.

        Returns:
            Description of the return value.
        """
        result = my_function(server_id, param)
        return f"Result: {result}"

    # 2. Access dependent module APIs (optional)
    if registry is not None:
        superset_api = registry.get_module_api("SupersetModule")
        if superset_api:
            manager = superset_api["ConnectionManager"]("/path/to/configs")
            # Use manager to interact with Superset...

    # 3. Expose this module's API to other modules
    if registry is not None:
        registry.register_module_api("MyModule", get_module_api())

# ── Implementation ────────────────────────────────────────────
def my_function(server_id: str, param: str) -> str:
    """Core logic — can be called by other modules via the registry."""
    return f"Processed {param} for {server_id}"


class MyClass:
    """A class exposed via the module API."""
    pass
```

### Step 3: Organize Tools in Submodules (Recommended)

For larger modules, split tools into separate files:

```python
# modules/MyModule/tools/handlers.py
async def my_tool_impl(manager, server_id: str, param: str) -> str:
    """Implementation with full docstring."""
    return f"Processed {param} for {server_id}"

# modules/MyModule/main.py
from .tools import handlers

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    @mcp.tool(name="my_tool")
    async def my_tool(server_id: str, param: str) -> str:
        """Short description — the full docstring comes from the impl."""
        return await handlers.my_tool_impl(manager, server_id, param)

    if registry is not None:
        registry.register_module_api("MyModule", get_module_api())
```

### Step 4: Restart the Server

The module will be auto-discovered on next startup. Check the logs:

```
INFO - Module load order (resolved dependencies): ['SupersetModule', 'MyModule']
INFO - Loaded module: SupersetModule (depends_on: [])
INFO - Loaded module: MyModule (depends_on: ['SupersetModule'])
INFO - Registered API for module: MyModule
```

Verify with the built-in tool:

```python
# Via MCP client or Swagger
list_loaded_modules()
# Returns: {"message": "Modules loaded", "loaded_modules": ["SupersetModule", "MyModule"]}

list_available_tools()
# Returns list including "my_tool"
```

---

## Frontend

The React/TypeScript frontend provides a web UI for:
- **Exporting** Superset dashboards (charts, datasets, databases, SQL queries)
- **Importing** dashboard exports to another Superset server
- **Validating** import readiness (checks for missing databases, datasets, chart issues)
- **Managing** Superset server configurations

See [Frontend API Reference](docs/frontend.rst) for full documentation.

---

## Testing

```bash
# Run all tests
pytest

# Run only unit tests (skip integration)
pytest -m "not integration"

# Run integration tests (requires Docker)
docker-compose up -d postgres-db
pytest -m "integration"

# Run specific test file
pytest tests/modules/DBAnalysis/test_postgres_strategy.py
```

---

## Observability

- **Prometheus** scrapes metrics from `/metrics`
- **Grafana** provides 3 pre-built dashboards: Usage, Resources Created, Performance & Errors
- **Error tracking** via in-memory ring buffer (last 100 errors) at `/errors`
- **Structured JSON logs** written to `logs/metrics.jsonl`

See `docs/observability.md` for details.

---

## Documentation

Build Sphinx docs (HTML + PDF):

```bash
cd docs
make html       # HTML at _build/html/index.html
make latexpdf   # PDF at _build/latex/AutomationMCPSuperset.pdf
```
