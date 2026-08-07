"""
Chart management tools for Apache Superset MCP integration.

This package provides comprehensive chart CRUD operations, validation,
and metadata discovery for Apache Superset.

Public API (re-exported from submodules):
    CRUD:
        - create_chart: Create a new Superset chart with full validation
        - update_chart: Update an existing chart's configuration
        - generate_chart: Generate a chart from a config dict and dataset

    Metadata:
        - list_charts: List all charts on a Superset server
        - get_chart_info: Get detailed information about a specific chart
        - get_standard_chart_params: Get standard params for a viz type
        - get_chart_creation_rules: Get expert rules for creating charts

    Data:
        - get_chart_preview: Get a visual preview URL for a chart
        - get_chart_data: Fetch underlying data for a chart

    Schema:
        - get_chart_type_schema: Get schema for a specific chart type
        - get_all_chart_schemas: Discover ALL chart types with their schemas
        - get_chart_api_info: Get metadata about the chart API

Internal helpers (underscore-prefixed, not part of public API):
    - _ensure_chart_types_cached, _is_known_chart_type
    - _resolve_viz_type, _validate_* helpers
    - _delete_chart, _validate_chart_on_datasource, _verify_chart_params_saved
    - _test_chart_data_endpoint, _extract_columns_from_dataset_response
    - etc.
"""

# CRUD operations
from .create_chart import create_chart
from .update_chart import update_chart
from .generate_chart import generate_chart

# Metadata
from .metadata import (
    list_charts,
    get_chart_info,
    get_standard_chart_params,
    get_chart_creation_rules,
)

# Data helpers
from .data import (
    get_chart_preview,
    get_chart_data,
)

# Schema discovery
from .schema import (
    get_chart_type_schema,
    get_all_chart_schemas,
    get_chart_api_info,
)

# Internal helpers (underscore-prefixed)
from .cache import (
    _ensure_chart_types_cached,
    _is_known_chart_type,
)
from .resolution import (
    _resolve_viz_type,
    _extract_columns_from_dataset_response,
    _extract_chart_ids_from_position_json,
    _validate_sankey_params,
)
from .validation import (
    _validate_metric_string_format,
    _validate_metrics_against_dataset,
)

from .lifecycle import (
    _delete_chart,
    _validate_chart_on_datasource,
    _verify_chart_params_saved,
)

from .data import (
    _test_chart_data_endpoint,
)

# Re-export all public functions from the old charts.py module
__all__ = [
    # CRUD
    "create_chart",
    "update_chart",
    "generate_chart",
    # Metadata
    "list_charts",
    "get_chart_info",
    "get_standard_chart_params",
    "get_chart_creation_rules",
    # Data
    "get_chart_preview",
    "get_chart_data",
    # Schema
    "get_chart_type_schema",
    "get_all_chart_schemas",
    "get_chart_api_info",
    # Internal helpers
    "_ensure_chart_types_cached",
    "_is_known_chart_type",
    "_resolve_viz_type",
    "_extract_columns_from_dataset_response",
    "_validate_metric_string_format",
    "_validate_metrics_against_dataset",
    "_extract_chart_ids_from_position_json",
    "_validate_sankey_params",
    "_delete_chart",
    "_validate_chart_on_datasource",
    "_verify_chart_params_saved",
    "_test_chart_data_endpoint",
]
