"""
Utility to map Google-style docstrings to FastAPI OpenAPI metadata.

This module bridges the gap between the Google-style docstrings (Description/Args/Returns)
added throughout the codebase and FastAPI's Swagger/OpenAPI documentation. FastAPI natively
uses the first line of a docstring as the ``summary`` but does not parse structured sections
like ``Args:`` and ``Returns:``. The ``docstring_to_openapi()`` function in this module
extracts those sections and formats them as Markdown for display in Swagger UI.
"""

import docstring_parser


def docstring_to_openapi(fn):
    """
    Parse a function's Google-style docstring and return OpenAPI-compatible metadata.

    Extracts the short description as the Swagger ``summary`` and builds a rich
    Markdown ``description`` from the long description, parameter list, and return
    value documentation. The resulting dict can be passed directly to FastAPI's
    ``add_api_route()`` as ``summary=`` and ``description=``.

    Args:
        fn: A callable whose ``__doc__`` follows the Google-style convention
            (sections: Description, Args, Returns).

    Returns:
        A dictionary with keys:
        - ``summary``: The first line of the docstring, used as the Swagger operation summary.
        - ``description``: A Markdown string combining the long description, parameter
          table, and return value documentation, for the Swagger operation description.
        - ``param_descriptions``: A dict mapping parameter names to their descriptions.
    """
    # Step 1: Parse the full docstring into structured components
    doc = docstring_parser.parse_from_object(fn)

    # Step 2: Collect all content sections in order for the Markdown description
    sections = []

    # Add the short description (first sentence/line) if present
    if doc.short_description:
        sections.append(doc.short_description)

    # Append the long description (everything between short description and Args:) if present
    if doc.long_description:
        sections.append("")
        sections.append(doc.long_description)

    # Step 3: Build a parameter table from the Args section
    if doc.params:
        sections.append("")
        sections.append("**Parameters:**")
        sections.append("")
        # Use a Markdown table for parameters within the description
        sections.append("| Parameter | Type | Description |")
        sections.append("|-----------|------|-------------|")
        for p in doc.params:
            type_name = p.type_name or "any"
            desc = (p.description or "").replace("\n", " ")
            sections.append(f"| `{p.arg_name}` | `{type_name}` | {desc} |")

    # Step 4: Add the Returns section if documented
    if doc.returns:
        sections.append("")
        sections.append("**Returns:**")
        sections.append("")
        # Include the return type if specified
        if doc.returns.type_name:
            sections.append(f"Type: `{doc.returns.type_name}`")
        if doc.returns.description:
            sections.append(doc.returns.description)

    # Step 5: Build the result dict for FastAPI route registration
    return {
        "summary": doc.short_description or fn.__name__.replace("_", " ").title(),
        "description": "\n".join(sections).strip(),
        "param_descriptions": {p.arg_name: p.description for p in doc.params if p.description},
    }
