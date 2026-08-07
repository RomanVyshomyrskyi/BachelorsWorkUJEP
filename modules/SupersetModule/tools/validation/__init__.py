"""
Validation tools for Superset chart parameters.

This package provides chart parameter validation and auto-fixing to prevent
Superset frontend errors. The public API consists of:

    validate_chart_params()     - Validate params against expected format
    auto_fix_chart_params()     - Auto-fix common parameter mistakes
    validate_datasource_compatibility() - Check datasource compatibility
    format_error_summary()      - Format errors into readable output
    format_validation_error()   - Full validation result formatting

Categories and helper functions are also available for advanced use.
"""

from .categories import (
    ADHOC_METRICS_ARRAY_TYPES,
    DATASOURCE_REQUIREMENTS,
    ENTITY_REQUIRED_TYPES,
    MIXED_METRICS_TYPES,
    NO_METRICS_TYPES,
    SANKEY_TYPES,
    SINGULAR_ADHOC_METRIC_TYPES,
    SINGULAR_STRING_METRIC_TYPES,
    STRING_METRICS_ARRAY_TYPES,
    TIME_BASED_TYPES,
    VALID_TIME_GRAINS,
)
from .compatibility import validate_datasource_compatibility
from .fixer import auto_fix_chart_params
from .fixer_core import apply_early_fixes
from .fixer_universal import apply_universal_fixes
from .formatter import format_error_summary, format_validation_error
from .helpers import (
    INVALID_METRIC_STRINGS,
    _build_adhoc_metric_from_string,
    _is_adhoc_metric_object,
    _is_string_metric,
    _parse_string_metric,
)
from .validator import validate_chart_params

__all__ = [
    # Main public functions
    "validate_chart_params",
    "auto_fix_chart_params",
    "apply_early_fixes",
    "apply_universal_fixes",
    "validate_datasource_compatibility",
    "format_error_summary",
    "format_validation_error",
    # Categories
    "SINGULAR_STRING_METRIC_TYPES",
    "SINGULAR_ADHOC_METRIC_TYPES",
    "STRING_METRICS_ARRAY_TYPES",
    "ADHOC_METRICS_ARRAY_TYPES",
    "MIXED_METRICS_TYPES",
    "NO_METRICS_TYPES",
    "ENTITY_REQUIRED_TYPES",
    "SANKEY_TYPES",
    "DATASOURCE_REQUIREMENTS",
    "TIME_BASED_TYPES",
    "VALID_TIME_GRAINS",
    # Helpers
    "INVALID_METRIC_STRINGS",
    "_is_adhoc_metric_object",
    "_is_string_metric",
    "_parse_string_metric",
    "_build_adhoc_metric_from_string",
]
