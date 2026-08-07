"""
Backward compatibility wrapper for rules package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.rules import (
    generate_robust_dashboard_layout,
    get_dashboard_creation_rules,
    get_chart_creation_rules,
)

__all__ = [
    'generate_robust_dashboard_layout',
    'get_dashboard_creation_rules',
    'get_chart_creation_rules',
]
