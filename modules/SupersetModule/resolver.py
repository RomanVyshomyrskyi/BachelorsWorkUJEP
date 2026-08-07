"""
Backward compatibility wrapper for resolver package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.resolver import resolve_chart_params
from modules.openapi_utils import _resolve_wrapper_impl as resolve_wrapper_impl

__all__ = [
    'resolve_chart_params',
    'resolve_wrapper_impl',
]
