
# How to run

1. From the repository root (where `docker-compose.dev.yml` lives), build and start everything:

```powershell
docker-compose -f .\docker-compose.dev.yml up --build
```

# Module Architecture

The project uses a **modular (plugin) architecture** via FastMCP with **cross-module dependency support**. Modules can declare dependencies on other modules and access their functionality through a shared `ModuleRegistry`.

## Module Discovery & Loading

1. **Core Server (`main.py`)**:
   - Scans the `modules` directory for subdirectories containing `main.py`
   - Reads `depends_on` from each module to build a dependency graph
   - Resolves load order using topological sort (Kahn's algorithm)
   - Loads modules in dependency order, passing the shared `ModuleRegistry`
   - Detects circular dependencies and aborts with a clear error

2. **Module Registry (`modules/registry.py`)**:
   - Central registry that stores each module's public API
   - Modules register their API via `registry.register_module_api(name, dict)`
   - Other modules retrieeve APIs via `registry.get_module_api(name)`
   - Provides `resolve_dependency_order()` for topological sorting

## Module Structure

Every module follows this convention:

```
modules/YourModule/
  __init__.py          # Package marker (empty)
  main.py              # Entry point: depends_on, get_module_api(), register()
  README.md            # Module documentation
  tools/               # Tool registration functions
  ...
```

### Required elements in `main.py`

```python
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

# 1. Dependency declaration (list of module folder names)
depends_on = ["DBAnalysis"]  # empty list if no dependencies

# 2. Public API surface exposed to other modules
def get_module_api():
    return {
        "my_function": my_function,
        "my_class": MyClass,
    }

# 3. Registration function (optional registry parameter)
def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    # Register MCP tools
    mcp.tool(name="my_tool")(my_tool)

    # Expose API to other modules
    if registry is not None:
        registry.register_module_api("YourModule", get_module_api())
```

## Cross-Module Access

A module that depends on another can access its API at runtime:

```python
depends_on = ["DBAnalysis"]

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    if registry is not None:
        db_api = registry.get_module_api("DBAnalysis")
        if db_api:
            strategy = db_api["get_db_strategy"](...)
```

### Dependency Resolution Rules

- Dependencies are declared via the top-level `depends_on` list in `main.py`
- The loader performs topological sorting; dependencies load first
- Circular dependencies raise a `ValueError` at startup
- Missing dependencies do not block loading (the depending module handles `None`)

## Current Modules & Dependencies

| Module | depends_on | Exposed API |
|---|---|---|
| `DBAnalysis` | (none) | `get_db_strategy`, `get_normalization_rules` |
| `SupersetModule` | (none) | `ConnectionManager`, `api_request`, `execute_request` |
| `StatisticalMethods` | (none) | All regression functions |
| `mermaid` | (none) | `get_mermaid_doc_content`, `get_mermaid_file_descriptions` |
| `LocalAPI` | (none) | (none) |

## Creating a New Module

1. Create the directory and files:

```bash
mkdir modules/your_module
touch modules/your_module/__init__.py
touch modules/your_module/main.py
```

2. Define `main.py` following the template above.

3. Add any sub-packages with their own `__init__.py` files.

# Full Testing Environment with Docker Compose

For a complete integration testing environment, there is a `docker-compose.yml` file that launches the FastMCP server along with instances of PostgreSQL, MariaDB, and MSSQL. This allows for end-to-end testing of modules like `DBAnalysis`.

The credentials for these databases are managed in the `.env` file.
