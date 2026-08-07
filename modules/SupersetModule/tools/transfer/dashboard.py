"""
Dashboard and chart transfer tools between Superset servers.

This file is kept for backward compatibility.
The main transfer logic is in transfer.py.
"""

# Re-export from transfer.py for backward compatibility
from modules.SupersetModule.tools.transfer.transfer import transfer_dashboard

__all__ = ["transfer_dashboard"]
