# Mermaid Module

This module provides documentation, syntax guides, and examples for [Mermaid](https://mermaid.js.org/), a JavaScript-based diagramming and charting tool.

---

## Detailed Functionality Reference

### Documentation and Example Tools (`main.py`)

#### `get_mermaid_doc_content(doc_filename)`
- **What it does**: Reads and returns the full text of a specific Mermaid documentation file from the `docs/` directory.
- **How it does it**: 
    1. Uses the `pathlib` library to resolve the absolute path to the `modules/mermaid/docs/` folder relative to the current script.
    2. Combines the directory path with the provided `doc_filename`.
    3. Performs a safety check to ensure the file exists and is indeed a file (not a directory).
    4. Opens the file in read-only mode and returns the content.

#### `get_mermaid_file_descriptions()`
- **What it does**: Scans the module's subdirectories and provides a summary of all available documentation and example diagrams.
- **How it does it**:
    1. **For Documentation (`docs/*.md`)**:
        - Iterates through all Markdown files in the `docs/` folder.
        - Opens each file and reads the first line (the H1 header) to extract the title.
        - Reads the second line to provide a brief "teaser" or context snippet.
        - Compiles this metadata into a JSON object with `filename`, `type: "documentation"`, and `description`.
    2. **For Examples (`examples/*.mmd`)**:
        - Iterates through all `.mmd` files in the `examples/` folder.
        - Generates a human-friendly description by replacing underscores in the filename with spaces (e.g., `flowchart_simple.mmd` becomes "Example for flowchart simple").
        - Compiles this into the same JSON object with `type: "example"`.
    3. Returns the final list as a formatted JSON string.

---

## Developer Documentation: Internal Logic

### Directory Structure
- **`docs/`**: contains `.md` files that serve as the "knowledge base" for the AI.
- **`examples/`**: contains `.mmd` files which are valid Mermaid code snippets.

### Tool Registration
The `register(mcp: FastMCP)` function in `main.py` is responsible for exposing these functions to the MCP server. It utilizes the `@mcp.tool` decorator to define the interface that external LLMs or clients will interact with.

### Extending the Module
Developers can add more diagram types by simply dropping a new `.md` file in `docs/` or a new `.mmd` file in `examples/`. No changes to `main.py` are required as the `get_mermaid_file_descriptions` function uses dynamic globbing to discover files at runtime.

---

## Cross-Module Interface

### Dependency Declaration
`depends_on = []` — this module has no dependencies on other modules.

### Public API (`get_module_api()`)
Other modules can access these via the `ModuleRegistry`:
- `get_mermaid_doc_content` — retrieves documentation file content
- `get_mermaid_file_descriptions` — lists available files with descriptions
