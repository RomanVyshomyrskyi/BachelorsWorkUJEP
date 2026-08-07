"""
Pre-chart data validation against actual dataset columns.

Prevents "Columns missing in dataset" errors by validating all column
references BEFORE the chart is sent to Superset API.

Provides structured validation results with:
- Missing columns with suggestions
- Temporal column validation for time series charts
- LLM-friendly error messages

Key functions:
    validate_chart_data_against_dataset: Main validation entry point
    format_validation_error: Format results into LLM-friendly error messages
"""

from modules.SupersetModule.tools.chart_validation.main import (
    validate_chart_data_against_dataset,
    TIME_SERIES_VIZ_TYPES,
    TEMPORAL_CHART_TYPES,
)
from modules.SupersetModule.tools.chart_validation.formatter import (
    format_validation_error,
)
from modules.SupersetModule.tools.chart_validation.checks import (
    _extract_columns_from_params,
    _extract_metric_columns,
    _find_column_suggestions,
)
from modules.SupersetModule.tools.chart_validation.validator import (
    _is_column_temporal,
    _get_temporal_columns,
)

__all__ = [
    "validate_chart_data_against_dataset",
    "format_validation_error",
    "TIME_SERIES_VIZ_TYPES",
    "TEMPORAL_CHART_TYPES",
    "_extract_columns_from_params",
    "_extract_metric_columns",
    "_find_column_suggestions",
    "_is_column_temporal",
    "_get_temporal_columns",
]
