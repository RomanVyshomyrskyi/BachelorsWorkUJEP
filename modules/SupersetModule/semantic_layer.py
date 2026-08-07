"""
Backward compatibility wrapper for semantic package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.semantic import (
    SemanticLayer,
    profile_table,
    suggest_metrics,
    suggest_dimensions,
    get_data_dictionary,
)

__all__ = [
    'SemanticLayer', 'profile_table',
    'suggest_metrics', 'suggest_dimensions',
    'get_data_dictionary',
]
