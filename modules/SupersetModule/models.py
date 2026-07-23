"""Module-level constants mapping resource types to Superset API endpoints.

This module provides lookup tables for all Superset REST API resource endpoints
and the transfer strategy (export_import vs json_copy) for each resource type.
These constants are used by the API client to construct proper request URLs
and by the transfer module to select the appropriate migration approach.

RESOURCE_ENDPOINTS:
    Maps simplified resource type names to their full Superset REST API
    endpoint paths. Used to build URLs like "GET /api/v1/chart/" for listing
    charts or "POST /api/v1/chart/" for creating charts.

TRANSFER_STRATEGY:
    Defines whether each resource type should use "export_import" (via Superset's
    built-in /export/ and /import/ endpoints) or "json_copy" (manual GET-list,
    GET-detail, POST-create sequence) during dashboard transfers. Resources using
    export_import benefit from built-in serialization that handles dependencies
    automatically, while json_copy provides more control but requires manual
    handling of referenced objects.
"""

# Map simplified resource names to their API endpoint base
RESOURCE_ENDPOINTS = {
    "advanced_data_type": "/api/v1/advanced_data_type",
    "annotation_layer": "/api/v1/annotation_layer",
    "assets": "/api/v1/assets",
    "async_event": "/api/v1/async_event",
    "available_domains": "/api/v1/available_domains",
    "cachekey": "/api/v1/cachekey",
    "chart": "/api/v1/chart",
    "css_template": "/api/v1/css_template",
    "dashboard": "/api/v1/dashboard",
    "database": "/api/v1/database",
    "dataset": "/api/v1/dataset",
    "datasource": "/api/v1/datasource",
    "embedded_dashboard": "/api/v1/embedded_dashboard",
    "explore": "/api/v1/explore",
    "log": "/api/v1/log",
    "query": "/api/v1/query",
    "saved_query": "/api/v1/saved_query",
    "report": "/api/v1/report",
    "rowlevelsecurity": "/api/v1/rowlevelsecurity",
    "security": "/api/v1/security",
    "sqllab": "/api/v1/sqllab",
    "tag": "/api/v1/tag",
    "user": "/api/v1/user",
}

# Transfer Strategies
# "export_import": Uses /export/ (GET) and /import/ (POST multipart)
# "json_copy": Uses / (GET list) -> /{pk} (GET detail) -> / (POST create json)
TRANSFER_STRATEGY = {
    "chart": "export_import",
    "dashboard": "export_import",
    "database": "export_import",
    "dataset": "export_import",
    "saved_query": "export_import",
    "assets": "export_import",

    # Fallback to json_copy for others where feasible
    "annotation_layer": "json_copy",
    "css_template": "json_copy",
    "report": "json_copy",
    "rowlevelsecurity": "json_copy",
}
