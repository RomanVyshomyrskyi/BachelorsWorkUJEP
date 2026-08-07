"""
Backward compatibility wrapper for mermaid package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.mermaid import (
    chart_to_mermaid,
    dashboard_to_mermaid,
)

__all__ = [
    'chart_to_mermaid',
    'dashboard_to_mermaid',
]
