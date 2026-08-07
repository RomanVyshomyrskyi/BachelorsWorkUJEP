"""
Backward compatibility wrapper for client package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.client import (
    authenticate,
    execute_request,
    ensure_auth,
)
from modules.SupersetModule.tools.client.auth import _get_csrf_token
from modules.SupersetModule.tools.client.helpers import _is_token_expired

__all__ = [
    'authenticate',
    'execute_request',
    'ensure_auth',
    '_get_csrf_token',
    '_is_token_expired',
]
