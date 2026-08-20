"""
Export all Superset resources to a single JSON structure.

This module provides functionality to export all dashboards, charts, datasets,
databases, CSS templates, and annotations from a Superset server into a
comprehensive JSON format suitable for backup, migration, or archival.

The exported JSON captures:
- All database connections with their configurations
- All datasets (both physical tables and virtual datasets with SQL)
- All charts with their params, viz_types, and datasource mappings
- All dashboards with their position_json and chart linkages
- CSS templates and annotation layers

MCP Tools Provided:
    - export_superset_config: Export all resources from a server to JSON
"""

import json
import time
from typing import Dict, Any, List, Optional
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth
from modules.SupersetModule.tools.resources import impl_list_resources, impl_get_resource
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


async def export_superset_config(
    manager: ConnectionManager,
    server_id: str,
    include_dashboards: bool = True,
    include_charts: bool = True,
    include_datasets: bool = True,
    include_databases: bool = True,
    include_css_templates: bool = True,
    include_annotations: bool = True,
) -> str:
    """Export all Superset resources from a server into a single JSON structure.

    Fetches all databases, datasets, charts, dashboards, CSS templates, and
    annotation layers from the specified Superset server and assembles them
    into a comprehensive export format. The export includes full resource
    details (params, metadata, configurations) with read-only fields stripped
    for clean serialization.

    Args:
        manager: ConnectionManager instance with Superset connection details.
        server_id: The ID of the Superset server to export from.
        include_dashboards: Whether to include dashboards (default: True).
        include_charts: Whether to include charts (default: True).
        include_datasets: Whether to include datasets (default: True).
        include_databases: Whether to include databases (default: True).
        include_css_templates: Whether to include CSS templates (default: True).
        include_annotations: Whether to include annotation layers (default: True).

    Returns:
        JSON string containing the complete export with all requested resources,
        metadata about the export (server_id, timestamp, version), and a
        summary of items exported by type.

    Examples:
        result = await export_superset_config(manager, "production")
        # Returns JSON with databases, datasets, charts, dashboards, etc.
    """
    mc = get_metrics()
    start_time = time.monotonic()

    ctx = manager.get_context(server_id)
    if not ctx:
        return log.collect(f"Error: Server '{server_id}' not found.")

    try:
        await ensure_auth(ctx)
    except Exception as e:
        return log.collect(f"Error: Authentication failed: {e}")

    export_data: Dict[str, Any] = {
        "export_version": "1.0",
        "source_server": server_id,
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "resources": {}
    }

    summary: Dict[str, int] = {}
    errors: List[str] = []

    # Export databases
    if include_databases:
        log.info(f"Exporting databases from {server_id}...")
        db_result = await impl_list_resources(manager, server_id, "database")
        db_data = _parse_json_result(db_result)
        if db_data:
            databases = []
            for db in db_data.get("result", []):
                db_detail_str = await impl_get_resource(manager, server_id, "database", db.get("id"))
                db_detail = _parse_json_result(db_detail_str)
                if db_detail:
                    db_obj = _sanitize_resource(db_detail.get("result", {}), ["id", "created_by", "changed_by", "created_on", "changed_on"])
                    databases.append(db_obj)
            export_data["resources"]["databases"] = databases
            summary["databases"] = len(databases)
            log.info(f"  Exported {len(databases)} databases")
        else:
            errors.append(f"Failed to list databases: {db_result}")

    # Export datasets
    if include_datasets:
        log.info(f"Exporting datasets from {server_id}...")
        ds_result = await impl_list_resources(manager, server_id, "dataset")
        ds_data = _parse_json_result(ds_result)
        if ds_data:
            datasets = []
            for ds in ds_data.get("result", []):
                ds_detail_str = await impl_get_resource(manager, server_id, "dataset", ds.get("id"))
                ds_detail = _parse_json_result(ds_detail_str)
                if ds_detail:
                    ds_obj = _sanitize_resource(ds_detail.get("result", {}), ["id", "created_by", "changed_by", "created_on", "changed_on"])
                    datasets.append(ds_obj)
            export_data["resources"]["datasets"] = datasets
            summary["datasets"] = len(datasets)
            log.info(f"  Exported {len(datasets)} datasets")
        else:
            errors.append(f"Failed to list datasets: {ds_result}")

    # Export charts
    if include_charts:
        log.info(f"Exporting charts from {server_id}...")
        chart_result = await impl_list_resources(manager, server_id, "chart")
        chart_data = _parse_json_result(chart_result)
        if chart_data:
            charts = []
            for ch in chart_data.get("result", []):
                chart_detail_str = await impl_get_resource(manager, server_id, "chart", ch.get("id"))
                chart_detail = _parse_json_result(chart_detail_str)
                if chart_detail:
                    chart_obj = _sanitize_resource(chart_detail.get("result", {}), ["id", "created_by", "changed_by", "created_on", "changed_on"])
                    charts.append(chart_obj)
            export_data["resources"]["charts"] = charts
            summary["charts"] = len(charts)
            log.info(f"  Exported {len(charts)} charts")
        else:
            errors.append(f"Failed to list charts: {chart_result}")

    # Export dashboards
    if include_dashboards:
        log.info(f"Exporting dashboards from {server_id}...")
        dash_result = await impl_list_resources(manager, server_id, "dashboard")
        dash_data = _parse_json_result(dash_result)
        if dash_data:
            dashboards = []
            for dash in dash_data.get("result", []):
                dash_detail_str = await impl_get_resource(manager, server_id, "dashboard", dash.get("id"))
                dash_detail = _parse_json_result(dash_detail_str)
                if dash_detail:
                    dash_obj = _sanitize_resource(dash_detail.get("result", {}), ["id", "created_by", "changed_by", "created_on", "changed_on"])
                    dashboards.append(dash_obj)
            export_data["resources"]["dashboards"] = dashboards
            summary["dashboards"] = len(dashboards)
            log.info(f"  Exported {len(dashboards)} dashboards")
        else:
            errors.append(f"Failed to list dashboards: {dash_result}")

    # Export CSS templates
    if include_css_templates:
        log.info(f"Exporting CSS templates from {server_id}...")
        css_result = await impl_list_resources(manager, server_id, "css_template")
        css_data = _parse_json_result(css_result)
        if css_data:
            css_templates = _sanitize_list(css_data.get("result", []), ["id", "created_by", "changed_by", "created_on", "changed_on"])
            export_data["resources"]["css_templates"] = css_templates
            summary["css_templates"] = len(css_templates)
            log.info(f"  Exported {len(css_templates)} CSS templates")
        else:
            errors.append(f"Failed to list CSS templates: {css_result}")

    # Export annotation layers
    if include_annotations:
        log.info(f"Exporting annotation layers from {server_id}...")
        ann_result = await impl_list_resources(manager, server_id, "annotation_layer")
        ann_data = _parse_json_result(ann_result)
        if ann_data:
            annotations = []
            for ann in ann_data.get("result", []):
                ann_detail_str = await impl_get_resource(manager, server_id, "annotation_layer", ann.get("id"))
                ann_detail = _parse_json_result(ann_detail_str)
                if ann_detail:
                    ann_obj = _sanitize_resource(ann_detail.get("result", {}), ["id", "created_by", "changed_by", "created_on", "changed_on"])
                    annotations.append(ann_obj)
            export_data["resources"]["annotations"] = annotations
            summary["annotations"] = len(annotations)
            log.info(f"  Exported {len(annotations)} annotation layers")
        else:
            errors.append(f"Failed to list annotation layers: {ann_result}")

    export_data["summary"] = summary
    export_data["errors"] = errors
    export_data["total_items"] = sum(summary.values())
    export_data["export_duration_ms"] = int((time.monotonic() - start_time) * 1000)

    mc.tool_calls.labels(tool="export_superset_config", status="success").inc()
    mc.tool_duration.labels(tool="export_superset_config").observe(time.monotonic() - start_time)

    return json.dumps(export_data, indent=2, default=str)


def _sanitize_resource(resource: Dict[str, Any], fields_to_remove: List[str]) -> Dict[str, Any]:
    """Remove read-only fields from a resource dict.

    Strips fields like id, created_by, changed_by, created_on, changed_on
    which should not be directly copied during import (IDs will be remapped).

    Args:
        resource: The resource dictionary to sanitize.
        fields_to_remove: List of field names to remove.

    Returns:
        New dictionary with specified fields removed.
    """
    return {k: v for k, v in resource.items() if k not in fields_to_remove}


def _sanitize_list(resources: List[Any], fields_to_remove: List[str]) -> List[Dict[str, Any]]:
    """Remove read-only fields from a list of resources.

    Args:
        resources: List of resource dictionaries.
        fields_to_remove: List of field names to remove.

    Returns:
        List of sanitized dictionaries.
    """
    return [_sanitize_resource(r if isinstance(r, dict) else {}, fields_to_remove) for r in resources]
