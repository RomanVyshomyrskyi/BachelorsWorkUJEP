"""
Mermaid documentation reader module.

Provides MCP tools for reading and listing Mermaid diagram documentation files
stored in the ``modules/mermaid/docs/`` and ``modules/mermaid/examples/`` directories.

This module enables MCP clients to:
- List all available Mermaid documentation and example files with descriptions.
- Read the full content of any documentation file.

Files are organised as:
- ``docs/<name>.md`` — Markdown documentation files (title derived from first line).
- ``examples/<name>.mmd`` — Raw Mermaid diagram files (`.mmd` extension).
"""

import os
import pathlib
import json
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

# This module has no dependencies on other modules
depends_on = []


def get_module_api():
    """
    Return a dictionary mapping tool names to their callable functions.

    This function is called by the ``ModuleRegistry`` when this module registers
    itself. The returned dict is stored so other modules can access these functions
    programmatically (not just via MCP tools).

    Returns:
        A dictionary with two keys:
        - ``"get_mermaid_doc_content"``: The function that reads a doc file.
        - ``"get_mermaid_file_descriptions"``: The function that lists all docs/examples.
    """
    return {
        "get_mermaid_doc_content": get_mermaid_doc_content,
        "get_mermaid_file_descriptions": get_mermaid_file_descriptions,
    }


def get_mermaid_doc_content(doc_filename: str) -> str:
    """
    Read and return the full content of a Mermaid documentation file.

    This function locates a Markdown file in the ``docs/`` subdirectory, reads
    its entire content, and returns it as a string. If the file does not exist
    or cannot be read, an error message is returned instead.

    Description:
        The function uses ``pathlib`` for path construction, which handles
        platform-specific path separators automatically. The file is read
        in text mode with UTF-8 encoding (default).

    Args:
        doc_filename: The name of the documentation file to read (e.g.
                      ``"architecture.md"``). The function will look for this
                      file in ``modules/mermaid/docs/``.

    Returns:
        The full file content as a string on success, or an error message
        string if the file is not found or cannot be read.
    """
    # Construct the path to the docs directory relative to this file's location
    docs_dir = pathlib.Path(__file__).parent / "docs"
    # Combine the docs directory with the requested filename
    file_path = docs_dir / doc_filename

    # Check if the file exists and is actually a file (not a directory)
    if not file_path.exists() or not file_path.is_file():
        return f"Error: Documentation file '{doc_filename}' not found."

    try:
        # Read the entire file content and return it
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        # Return a descriptive error message if reading fails
        return f"Error reading file '{doc_filename}': {str(e)}"


def get_mermaid_file_descriptions() -> str:
    """
    List all available Mermaid documentation and example files with descriptions.

    This function scans the ``docs/`` and ``examples/`` subdirectories, reads
    metadata from each file (title from the first line for docs, filename for
    examples), and returns a JSON array of file descriptions.

    Description:
        For ``.md`` documentation files, the first line is expected to be a
        Markdown heading (``# Title``). The title is extracted and used as the
        file's display name. The second line (if present and different from the
        first) is used as a brief description snippet.

        For ``.mmd`` example files, the filename is used as a label with spaces
        replacing underscores.

    Returns:
        A JSON string (pretty-printed with 2-space indentation) containing a
        list of file description objects. Each object has:
        - ``"filename"``: The name of the file.
        - ``"type"``: Either ``"documentation"`` or ``"example"``.
        - ``"description"``: A human-readable description of the file's purpose.
    """
    # Paths to the docs and examples directories
    docs_dir = pathlib.Path(__file__).parent / "docs"
    examples_dir = pathlib.Path(__file__).parent / "examples"

    file_descriptions = []

    # Scan for all Markdown documentation files in the docs directory
    for doc_file in docs_dir.glob("*.md"):
        try:
            # Open and read the first two lines for metadata extraction
            with open(doc_file, "r") as f:
                first_line = f.readline().strip()
                # Extract title from Markdown heading (e.g., "# Architecture" -> "Architecture")
                title = first_line.lstrip("# ").strip() if first_line.startswith("#") else doc_file.name
                # Start with a generic description based on the title
                description = f"Documentation for {title.lower()}"

                # Read the second line for a potential description snippet
                second_line = f.readline().strip()
                # If the second line exists and differs from the title, append it as a snippet
                if second_line and second_line != first_line:
                    description += f": {second_line[:100]}..."
            # Add the documentation file entry to the results list
            file_descriptions.append({
                "filename": doc_file.name,
                "type": "documentation",
                "description": description
            })
        except Exception as e:
            # If reading fails, add an error entry instead
            file_descriptions.append({
                "filename": doc_file.name,
                "type": "documentation",
                "description": f"Error reading description: {str(e)}"
            })

    # Scan for all Mermaid diagram files in the examples directory
    for example_file in examples_dir.glob("*.mmd"):
        # Build a description from the filename (replace underscores with spaces)
        file_descriptions.append({
            "filename": example_file.name,
            "type": "example",
            "description": f"Example Mermaid diagram for {example_file.stem.replace('_', ' ')}."
        })

    # Return the complete list as a pretty-printed JSON string
    return json.dumps(file_descriptions, indent=2)


def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    """
    Register this module's tools with the MCP server and API with the registry.

    This function is called by the main module loader during startup. It registers
    two MCP tools:
    - ``get_mermaid_doc_content``: Reads a specific documentation file.
    - ``get_mermaid_file_descriptions``: Lists all available documentation files.

    If a ``ModuleRegistry`` is provided, the module's API is also registered.

    Args:
        mcp: The ``FastMCP`` server instance to register tools with.
        registry: An optional ``ModuleRegistry`` instance for registering the
                  module's API. If ``None``, the API is not registered.
    """
    # Register the doc content reader as an MCP tool
    mcp.tool(name="get_mermaid_doc_content")(get_mermaid_doc_content)
    # Register the file descriptions lister as an MCP tool
    mcp.tool(name="get_mermaid_file_descriptions")(get_mermaid_file_descriptions)

    # If a registry is provided, register this module's API for inter-module access
    if registry is not None:
        registry.register_module_api("mermaid", get_module_api())
