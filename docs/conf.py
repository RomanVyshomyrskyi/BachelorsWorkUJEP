"""Sphinx configuration for AutomationMCP Superset — API documentation.

Build with:  cd docs && make html
Output at:  docs/_build/html/index.html
"""

import os
import sys

sys.path.insert(0, os.path.abspath(".."))

project = "AutomationMCP Superset"
copyright = "2025, DCUK"
author = "DCUK"
release = "1.1.0"

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
]

napoleon_google_docstring = True
napoleon_numpy_docstring = False
napoleon_include_init_with_doc = True
napoleon_use_param = True
napoleon_use_rtype = True

autodoc_default_options = {
    "members": True,
    "undoc-members": False,
    "show-inheritance": True,
    "special-members": "__init__",
}

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_title = "AutomationMCP Superset Docs"
