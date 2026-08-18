"""Sphinx configuration for AutomationMCP Superset — API documentation.

Build with:  cd docs && make html
Output at:  docs/_build/html/index.html
"""

import os
import sys
import warnings

sys.path.insert(0, os.path.abspath(".."))

# Suppress Pydantic field-shadowing warnings that clutter the build log
warnings.filterwarnings("ignore", message="Field name .* shadows an attribute in parent")

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

autodoc_mock_imports = [
    "fastmcp",
    "httpx",
    "pydantic",
    "prometheus_client",
    "pandas",
    "numpy",
    "plotly",
    "matplotlib",
    "psycopg2",
    "mysql.connector",
    "pyodbc",
    "sqlparse",
    "scipy",
    "sklearn",
    "kaleido",
    "uvicorn",
    "fastapi",
    "docstring_parser",
]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
}

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]
suppress_warnings = ["autodoc.imported_member"]

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_css_files = ["custom.css"]
html_title = "AutomationMCP Superset Docs"

# PDF / LaTeX settings
latex_elements = {
    "papersize": "a4paper",
    "pointsize": "10pt",
    "preamble": r"""
\usepackage{enumitem}
\setlistdepth{9}
\renewlist{itemize}{itemize}{9}
\renewlist{enumerate}{enumerate}{9}
\setlist[itemize,1]{label=\textbullet}
\setlist[itemize,2]{label=\textbullet}
\setlist[itemize,3]{label=\textbullet}
\setlist[itemize,4]{label=\textbullet}
\setlist[itemize,5]{label=\textbullet}
\setlist[itemize,6]{label=\textbullet}
\setlist[itemize,7]{label=\textbullet}
\setlist[itemize,8]{label=\textbullet}
\setlist[itemize,9]{label=\textbullet}
""",
}
latex_documents = [
    ("index", "AutomationMCPSuperset.tex", "AutomationMCP Superset Documentation",
     "DCUK", "manual", True),
]
