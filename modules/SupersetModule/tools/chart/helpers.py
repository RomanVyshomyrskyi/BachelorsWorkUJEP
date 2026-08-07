"""
Helper utilities for chart management operations.

Shared constants and utility functions used across chart modules.
"""

import os
import json
import re
import logging
from typing import List, Dict, Any, Optional
from modules.SupersetModule.chart_strategies import TYPE_MAP

logger = logging.getLogger(__name__)

# Numeric types for type compatibility checking
NUMERIC_TYPES = {
    "int", "int2", "int4", "int8", "int16", "int32", "int64",
    "integer", "smallint", "bigint", "tinyint",
    "float", "float4", "float8", "double", "double precision",
    "decimal", "numeric", "number", "real",
    "money",
}

# Cache configuration
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "chart_schemas.json")
CHART_TYPES_CACHE_FILE = os.path.join(CACHE_DIR, "known_chart_types.json")
CACHE_TTL_SECONDS = 86400  # 24 hours

# Debug log path
_debug_log_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "logs", "chart_debug.log")
try:
    os.makedirs(os.path.dirname(_debug_log_path), exist_ok=True)
    _debug_handler = logging.FileHandler(_debug_log_path)
    _debug_handler.setLevel(logging.DEBUG)
    _debug_handler.setFormatter(logging.Formatter(
        '%(asctime)s [%(levelname)s] %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
    ))
    logger.addHandler(_debug_handler)
    logger.info("Chart debug log initialized at %s", _debug_log_path)
except (OSError, PermissionError) as e:
    print(f"WARNING: Could not create chart debug log: {e}", file=__import__('sys').stderr)
