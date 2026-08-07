"""
Semantic layer for Apache Superset database introspection and profiling.

Description:
    Provides tools for analyzing database tables: column classification, statistical
    profiling, metric/dimension suggestion, and data dictionary generation. All functions
    execute SQL queries against PostgreSQL/MariaDB databases via Superset's SQL Lab.

Modules:
    - Column classification: Classifies columns as numeric, text, date, boolean, or other
    - Table profiling: Generates statistics (count, null%, min/max/avg, distinct, stddev)
    - Metric suggestion: Recommends aggregatable columns with SUM/AVG/COUNT/MIN/MAX
    - Dimension suggestion: Recommends grouping/filtering columns with usage hints
    - Data dictionary: Full table metadata with classification and optional statistics
"""

# Re-export the SemanticLayer class
from modules.SupersetModule.tools.semantic.layer import SemanticLayer

# Re-export async functions for backward compatibility
from modules.SupersetModule.tools.semantic.layer import profile_table
from modules.SupersetModule.tools.semantic.suggest import suggest_metrics, suggest_dimensions
from modules.SupersetModule.tools.semantic.dictionary import get_data_dictionary

# Re-export helper constants for backward compatibility
from modules.SupersetModule.tools.semantic.helpers import (
    NUMERIC_KEYWORDS,
    TEXT_KEYWORDS,
    DATE_KEYWORDS,
    BOOLEAN_KEYWORDS,
    _classify_column,
    _extract_numeric,
    _extract_text,
    _extract_date,
    _quote,
    _escape,
    _is_metric_candidate,
    _is_dimension_candidate,
)

# Internal alias for test mocking (tools/semantic.py delegation pattern)
_profile_table = profile_table

__all__ = [
    "SemanticLayer",
    "profile_table",
    "_profile_table",
    "suggest_metrics",
    "suggest_dimensions",
    "get_data_dictionary",
    "NUMERIC_KEYWORDS",
    "TEXT_KEYWORDS",
    "DATE_KEYWORDS",
    "BOOLEAN_KEYWORDS",
    "_classify_column",
    "_extract_numeric",
    "_extract_text",
    "_extract_date",
    "_quote",
    "_escape",
    "_is_metric_candidate",
    "_is_dimension_candidate",
]
