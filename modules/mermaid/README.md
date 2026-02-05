# Mermaid Module

This module provides comprehensive documentation, syntax guides, and examples for [Mermaid](https://mermaid.js.org/), a JavaScript-based diagramming and charting tool that renders Markdown-inspired text definitions into dynamic diagrams.

The goal of this module is to serve as a quick reference and learning resource for generating various types of diagrams (flowcharts, sequence diagrams, Gantt charts, etc.) using simple text syntax.

## Contents

-   **`docs/`**: Detailed documentation and syntax guides for different Mermaid diagram types.
-   **`examples/`**: A collection of `.mmd` files demonstrating various Mermaid diagrams.
-   **`resources/`**: Additional resources, links, or helper files related to Mermaid.

## Available Tools

### `get_mermaid_doc_content(doc_filename: str)`

Retrieves the content of a specific Mermaid documentation file. This allows you to programmatically access the syntax guides and explanations provided within this module.

**Parameters:**

-   `doc_filename` (string, required): The name of the documentation file you want to retrieve.
    *Example:* `syntax_overview.md`, `flowchart_syntax.md`, `sequence_diagram_syntax.md`, etc.

**Returns:**

The content of the requested documentation file as a string, or an error message if the file is not found or cannot be read.

### `get_mermaid_file_descriptions()`

Lists all available Mermaid documentation and example files with a short description of their content. This tool is useful for understanding what documentation and examples are available, helping you or other LLMs to identify relevant files for specific queries.

**Parameters:**

-   None

**Returns:**

A JSON string containing a list of objects, where each object represents a file and includes its `filename`, `type` (e.g., "documentation", "example"), and a brief `description`.
