import os
import pathlib
import json
from typing import Optional
from fastmcp import FastMCP
from modules.registry import ModuleRegistry

depends_on = []

def get_module_api():
    return {
        "get_mermaid_doc_content": get_mermaid_doc_content,
        "get_mermaid_file_descriptions": get_mermaid_file_descriptions,
    }

def get_mermaid_doc_content(doc_filename: str) -> str:
    docs_dir = pathlib.Path(__file__).parent / "docs"
    file_path = docs_dir / doc_filename

    if not file_path.exists() or not file_path.is_file():
        return f"Error: Documentation file '{doc_filename}' not found."

    try:
        with open(file_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file '{doc_filename}': {str(e)}"

def get_mermaid_file_descriptions() -> str:
    docs_dir = pathlib.Path(__file__).parent / "docs"
    examples_dir = pathlib.Path(__file__).parent / "examples"

    file_descriptions = []

    for doc_file in docs_dir.glob("*.md"):
        try:
            with open(doc_file, "r") as f:
                first_line = f.readline().strip()
                title = first_line.lstrip("# ").strip() if first_line.startswith("#") else doc_file.name
                description = f"Documentation for {title.lower()}"

                second_line = f.readline().strip()
                if second_line and second_line != first_line:
                    description += f": {second_line[:100]}..."
            file_descriptions.append({
                "filename": doc_file.name,
                "type": "documentation",
                "description": description
            })
        except Exception as e:
            file_descriptions.append({
                "filename": doc_file.name,
                "type": "documentation",
                "description": f"Error reading description: {str(e)}"
            })

    for example_file in examples_dir.glob("*.mmd"):
        file_descriptions.append({
            "filename": example_file.name,
            "type": "example",
            "description": f"Example Mermaid diagram for {example_file.stem.replace('_', ' ')}."
        })

    return json.dumps(file_descriptions, indent=2)

def register(mcp: FastMCP, registry: Optional[ModuleRegistry] = None):
    mcp.tool(name="get_mermaid_doc_content")(get_mermaid_doc_content)
    mcp.tool(name="get_mermaid_file_descriptions")(get_mermaid_file_descriptions)

    if registry is not None:
        registry.register_module_api("mermaid", get_module_api())
