"""
Backward compatibility wrapper for superset_validation package.
All imports are re-exported from the refactored submodules.
"""
from modules.SupersetModule.tools.validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
    format_validation_error,
    validate_datasource_compatibility,
)
from modules.SupersetModule.tools.validation.categories import (
    SINGULAR_STRING_METRIC_TYPES,
    SINGULAR_ADHOC_METRIC_TYPES,
    STRING_METRICS_ARRAY_TYPES,
    ADHOC_METRICS_ARRAY_TYPES,
    MIXED_METRICS_TYPES,
    NO_METRICS_TYPES,
    ENTITY_REQUIRED_TYPES,
    SANKEY_TYPES,
    DATASOURCE_REQUIREMENTS,
    TIME_BASED_TYPES,
)

__all__ = [
    'validate_chart_params',
    'auto_fix_chart_params',
    'format_error_summary',
    'format_validation_error',
    'validate_datasource_compatibility',
    'SINGULAR_STRING_METRIC_TYPES',
    'SINGULAR_ADHOC_METRIC_TYPES',
    'STRING_METRICS_ARRAY_TYPES',
    'ADHOC_METRICS_ARRAY_TYPES',
    'MIXED_METRICS_TYPES',
    'NO_METRICS_TYPES',
    'ENTITY_REQUIRED_TYPES',
    'SANKEY_TYPES',
    'DATASOURCE_REQUIREMENTS',
    'TIME_BASED_TYPES',
]
