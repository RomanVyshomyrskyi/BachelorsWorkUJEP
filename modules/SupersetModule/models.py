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
