import json
import logging
import httpx
import time
import os
from typing import Optional, Union, Dict, Any, List
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.exceptions import ChartError
from modules.SupersetModule.schemas.chart import (
    ChartListItem,
    ChartDetail,
    ChartPreviewResponse,
    ChartDataResponse,
    ChartTypeSchema,
 )
from modules.SupersetModule.schemas.common import SupersetListResponse, SupersetDetailResponse
from modules.SupersetModule import rules
from modules.SupersetModule.superset_validation import (
    validate_chart_params,
    auto_fix_chart_params,
    format_error_summary,
 )
from modules.SupersetModule.superset_mermaid import chart_to_mermaid
from modules.SupersetModule.resolver import resolve_chart_params
from modules.SupersetModule.chart_strategies import TYPE_MAP
from modules.metrics import get_metrics
from modules.SupersetModule.tools.chart_validation import (
    validate_chart_data_against_dataset,
    format_validation_error,
)

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache")
CACHE_FILE = os.path.join(CACHE_DIR, "chart_schemas.json")
CHART_TYPES_CACHE_FILE = os.path.join(CACHE_DIR, "known_chart_types.json")

logger = logging.getLogger(__name__)
CACHE_TTL_SECONDS = 86400  # 24 hours


async def _ensure_chart_types_cached(manager: ConnectionManager, server_id: str) -> List[str]:
    """
    Ensure chart types cache exists and is fresh.
    Returns list of known chart type names.
    Auto-fetches if cache is missing or expired.
    """
    import asyncio

    # Check cache
    if os.path.isfile(CHART_TYPES_CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CHART_TYPES_CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CHART_TYPES_CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("chart_types", [])
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch from Superset API
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception:
        # Fallback to local TYPE_MAP
        return list(TYPE_MAP.values())

    # Extract chart types from _info
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        # Check form_data.properties.viz_type.enum
        fd = properties.get("form_data", {})
        if isinstance(fd, dict):
            fd_props = fd.get("properties", {})
            viz_type = fd_props.get("viz_type", {})
            if isinstance(viz_type, dict):
                enum_vals = viz_type.get("enum", [])
                if enum_vals:
                    chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            form_data_prop = properties.get("form_data", {})
            if isinstance(form_data_prop, dict):
                fd_viz = form_data_prop.get("viz_type", {})
                if isinstance(fd_viz, dict):
                    enum_vals = fd_viz.get("enum", [])
                    if enum_vals:
                        chart_types = [str(v) for v in enum_vals]

        if not chart_types:
            ct = properties.get("chart_types", [])
            if isinstance(ct, list) and ct:
                chart_types = [str(c) for c in ct]

        if not chart_types:
            for key, val in properties.items():
                if isinstance(val, dict) and "enum" in val:
                    enum_vals = val.get("enum", [])
                    if isinstance(enum_vals, list) and len(enum_vals) > 2:
                        chart_types = [str(v) for v in enum_vals]
                        break

    if not chart_types:
        chart_types = list(TYPE_MAP.values())

    # Save cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CHART_TYPES_CACHE_FILE, "w") as f:
            json.dump({
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "chart_types": chart_types,
            }, f, indent=2)
    except OSError:
        pass

    return chart_types


def _is_known_chart_type(chart_types: List[str], viz_type: str) -> bool:
    """Check if a viz_type is known (either in dynamic cache or local TYPE_MAP)."""
    if viz_type in chart_types:
        return True
    # Also check against local TYPE_MAP values as fallback
    return viz_type in TYPE_MAP.values()


async def get_chart_api_info(manager: ConnectionManager, server_id: str) -> str:
    """
    Retrieves metadata about the chart API.
    """
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")

def _resolve_viz_type(viz_type: str) -> str:
    """Resolve a generic viz_type to the actual Superset viz_type using TYPE_MAP."""
    return TYPE_MAP.get(viz_type, viz_type)

def _extract_columns_from_dataset_response(response_str: str) -> List[Dict[str, Any]]:
    """Extract columns list from dataset API response."""
    try:
        data = json.loads(response_str)
        result = data.get("result", {})
        if isinstance(result, dict):
            columns = result.get("columns", [])
            if isinstance(columns, list):
                return columns
        return []
    except (json.JSONDecodeError, TypeError):
        return []

async def create_chart(
    manager: ConnectionManager,
    server_id: str,
    slice_name: str,
    viz_type: str,
    datasource_id: int,
    datasource_type: str,
    params: str,
    description: Optional[str] = None
 ) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Ensure chart types cache is available
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        actual_viz_type = _resolve_viz_type(viz_type)

        # Validate viz_type against known chart types
        if not _is_known_chart_type(known_types, actual_viz_type):
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
            mc.record_error(tool="superset_create_chart", error_message=f"Unknown chart type '{actual_viz_type}'")
            return ChartError(
                f"Chart type '{actual_viz_type}' is not recognized.",
                details=f"Please call 'superset_get_all_chart_schemas' first to discover all available chart types. Known types: {', '.join(known_types[:20])}{'...' if len(known_types) > 20 else ''}",
            ).to_json()
        params_dict = json.loads(params) if params else {}
        fixed_params = auto_fix_chart_params(actual_viz_type, params_dict)
        
        dataset_columns = []
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{datasource_id}")
            dataset_columns = _extract_columns_from_dataset_response(dataset_response)
        except Exception:
            pass
        
        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                warning = "Column name fixes: " + "; ".join(column_warnings)
            else:
                warning = None
            
            # NEW: Validate chart data against dataset BEFORE creating
            logger.info(f"Running pre-chart data validation for datasource_id={datasource_id}")
            validation_result = validate_chart_data_against_dataset(
                fixed_params, dataset_columns, actual_viz_type
            )
            
            if not validation_result["is_valid"]:
                logger.warning(
                    f"Chart validation failed for '{slice_name}': "
                    f"{len(validation_result['errors'])} errors, "
                    f"{len(validation_result['missing_columns'])} missing columns"
                )
                error_msg = format_validation_error(validation_result, slice_name, datasource_id)
                
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
                mc.record_error(
                    tool="superset_create_chart",
                    error_message=f"Missing columns in dataset: {len(validation_result['missing_columns'])} columns not found"
                )
                
                return ChartError(
                    error_msg["title"],
                    details=error_msg["body"],
                    status_code=400,
                ).to_json()
            
            # Merge validation warnings
            if validation_result.get("warnings"):
                validation_warnings = "; ".join(validation_result["warnings"])
                if warning:
                    warning = warning + " | Validation: " + validation_warnings
                else:
                    warning = "Validation: " + validation_warnings
        else:
            warning = None
            logger.warning(
                f"Could not fetch dataset columns for datasource_id={datasource_id}, "
                f"skipping column validation"
            )
        
        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None
        
        if validation_errors:
            if warning:
                warning = warning + " | " + validation_errors
            else:
                warning = "Validation: " + validation_errors

        # Ensure datasource_id is in params (required by Superset frontend)
        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = datasource_id
        # Ensure datasource field is set
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{datasource_id}__table"
        # Ensure datasource_type is set
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = datasource_type

        chart_payload = {
            "slice_name": slice_name,
            "description": description,
            "viz_type": actual_viz_type,
            "datasource_id": datasource_id,
            "datasource_type": datasource_type,
            "params": json.dumps(fixed_params),
        }

        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

        if warning:
            result["_validation_warning"] = warning

        try:
            result["_mermaid_graph"] = chart_to_mermaid(actual_viz_type, fixed_params, slice_name)
        except Exception:
            result["_mermaid_graph"] = None

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="success").inc()
        mc.tool_duration.labels(tool="superset_create_chart").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="chart").inc()
        return json.dumps(result, indent=2)
    except json.JSONDecodeError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"Invalid JSON in params: {e}")
        return ChartError(f"Invalid JSON in params: {e}", details=str(e)).to_json()
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_create_chart", status="error").inc()
        mc.record_error(tool="superset_create_chart", error_message=f"HTTP {e.response.status_code} creating chart", status_code=e.response.status_code)
        return ChartError(
            f"HTTP {e.response.status_code} creating chart",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
       return ChartError(f"Unexpected error creating chart: {e}", details=str(e)).to_json()

async def update_chart(
    manager: ConnectionManager,
    server_id: str,
    chart_id: int,
    json_body: str
) -> str:
    return await impl_superset_api(manager, server_id, "PUT", f"/api/v1/chart/{chart_id}", json_body=json_body)

def get_standard_chart_params(viz_type: str, datasource_id: int, overrides_json: Optional[str] = None) -> str:
    """
    Returns a JSON string of standard parameters for a given visualization type.
    """
    overrides = json.loads(overrides_json) if overrides_json else {}
    params = rules.get_standard_chart_params(viz_type, datasource_id, **overrides)
    return json.dumps(params, indent=2)

def get_chart_creation_rules() -> str:
    """Returns the expert rules for creating functional Superset charts."""
    return rules.get_chart_creation_rules()


async def list_charts(manager: ConnectionManager, server_id: str) -> str:
    return await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/")


async def get_chart_info(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    return await impl_superset_api(
       manager, server_id, "GET", f"/api/v1/chart/{chart_id}"
    )

async def generate_chart(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: int,
    config: str,
    slice_name: Optional[str] = None,
    save_chart: bool = True,
    description: Optional[str] = None
 ) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"Server '{server_id}' not found.")
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Ensure chart types cache is available
    known_types = await _ensure_chart_types_cached(manager, server_id)

    start_time = time.monotonic()
    try:
        chart_config = json.loads(config) if config else {}

        viz_type = chart_config.get("viz_type", "table")
        actual_viz_type = _resolve_viz_type(viz_type)

        # Validate viz_type against known chart types
        if not _is_known_chart_type(known_types, actual_viz_type):
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
            mc.record_error(tool="superset_generate_chart", error_message=f"Unknown chart type '{actual_viz_type}'")
            return ChartError(
                f"Chart type '{actual_viz_type}' is not recognized.",
                details=f"Please call 'superset_get_all_chart_schemas' first to discover all available chart types. Known types: {', '.join(known_types[:20])}{'...' if len(known_types) > 20 else ''}",
            ).to_json()
        form_data: Dict[str, Any] = {
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "datasource": f"{dataset_id}__table",
        }
        form_data.update(chart_config)
        form_data["viz_type"] = actual_viz_type

        fixed_params = auto_fix_chart_params(actual_viz_type, form_data)
        
        dataset_columns = []
        try:
            dataset_response = await impl_superset_api(manager, server_id, "GET", f"/api/v1/dataset/{dataset_id}")
            dataset_columns = _extract_columns_from_dataset_response(dataset_response)
        except Exception:
            pass
        
        if dataset_columns:
            fixed_params, column_warnings = resolve_chart_params(fixed_params, dataset_columns)
            if column_warnings:
                validation_warning = "Column fixes: " + "; ".join(column_warnings)
            else:
                validation_warning = None
            
            # NEW: Validate chart data against dataset BEFORE creating
            logger.info(f"Running pre-chart data validation for dataset_id={dataset_id}")
            validation_result = validate_chart_data_against_dataset(
                fixed_params, dataset_columns, actual_viz_type
            )
            
            if not validation_result["is_valid"]:
                logger.warning(
                    f"Chart validation failed for '{slice_name}': "
                    f"{len(validation_result['errors'])} errors, "
                    f"{len(validation_result['missing_columns'])} missing columns"
                )
                error_msg = format_validation_error(validation_result, slice_name, dataset_id)
                
                mc = get_metrics()
                mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
                mc.record_error(
                    tool="superset_generate_chart",
                    error_message=f"Missing columns in dataset: {len(validation_result['missing_columns'])} columns not found"
                )
                
                return ChartError(
                    error_msg["title"],
                    details=error_msg["body"],
                    status_code=400,
                ).to_json()
            
            # Merge validation warnings
            if validation_result.get("warnings"):
                validation_warnings = "; ".join(validation_result["warnings"])
                if validation_warning:
                    validation_warning = validation_warning + " | Validation: " + validation_warnings
                else:
                    validation_warning = "Validation: " + validation_warnings
        else:
            validation_warning = None
            logger.warning(
                f"Could not fetch dataset columns for dataset_id={dataset_id}, "
                f"skipping column validation"
            )
        
        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None
        
        if validation_errors and not validation_warning:
            validation_warning = "Validation: " + validation_errors
        elif validation_errors and validation_warning:
            validation_warning = validation_warning + " | " + validation_errors

        if not save_chart:
            base_url = ctx.config.base_url.rstrip("/")
            explore_url = f"{base_url}/explore/?form_data={json.dumps(fixed_params)}"
            mc = get_metrics()
            mc.tool_calls.labels(tool="superset_generate_chart", status="success").inc()
            mc.tool_duration.labels(tool="superset_generate_chart").observe(time.monotonic() - start_time)
            result = {
                "url": explore_url,
                "saved": False,
                "config": fixed_params,
            }
            if validation_warning:
                result["_validation_warning"] = validation_warning
            return json.dumps(result, indent=2)

        chart_name = slice_name or f"Chart from dataset {dataset_id}"

        # Ensure datasource_id is in params
        if "datasource_id" not in fixed_params or fixed_params["datasource_id"] is None:
            fixed_params["datasource_id"] = dataset_id
        if "datasource" not in fixed_params:
            fixed_params["datasource"] = f"{dataset_id}__table"
        if "datasource_type" not in fixed_params:
            fixed_params["datasource_type"] = "table"

        chart_payload = {
            "slice_name": chart_name,
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "viz_type": actual_viz_type,
            "params": json.dumps(fixed_params),
        }
        if description:
            chart_payload["description"] = description

        endpoint = "/api/v1/chart/"
        resp = await execute_request(ctx, "POST", endpoint, json=chart_payload)
        resp.raise_for_status()
        result = resp.json()

        try:
            result["_mermaid_graph"] = chart_to_mermaid(actual_viz_type, fixed_params, chart_name)
        except Exception:
            result["_mermaid_graph"] = None

        if validation_warning:
            result["_validation_warning"] = validation_warning

        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="success").inc()
        mc.tool_duration.labels(tool="superset_generate_chart").observe(time.monotonic() - start_time)
        mc.resources_created.labels(resource_type="chart").inc()
        return json.dumps({
            "saved": True,
            "chart_id": result.get("id"),
            "slice_name": chart_name,
            "url": f"{ctx.config.base_url.rstrip('/')}/chart/{result.get('id')}/",
            "result": result
        }, indent=2)

    except json.JSONDecodeError:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message="'config' is not a valid JSON string.")
        return ChartError("'config' is not a valid JSON string.", details=config).to_json()
    except httpx.HTTPStatusError as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=f"HTTP {e.response.status_code} generating chart", status_code=e.response.status_code)
        return ChartError(
            f"HTTP {e.response.status_code} generating chart",
            status_code=e.response.status_code,
            details=e.response.text,
        ).to_json()
    except Exception as e:
        mc = get_metrics()
        mc.tool_calls.labels(tool="superset_generate_chart", status="error").inc()
        mc.record_error(tool="superset_generate_chart", error_message=str(e))
        return ChartError(f"Unexpected error generating chart: {e}", details=str(e)).to_json()


async def get_chart_preview(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       base_url = ctx.config.base_url.rstrip("/")
       preview_url = f"{base_url}/explore/?slice_id={chart_id}"
       embed_url = f"{base_url}/superset/slice/{chart_id}/"

       return ChartPreviewResponse(
           preview_url=preview_url,
           chart_id=int(chart_id),
           embed_url=embed_url,
       ).model_dump_json(indent=2)
    except Exception as e:
       return ChartError(f"Unexpected error getting chart preview: {e}", details=str(e)).to_json()


async def get_chart_data(
    manager: ConnectionManager,
    server_id: str,
    chart_id: Union[int, str]
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
       endpoint = f"/api/v1/chart/{chart_id}/data/"
       resp = await execute_request(ctx, "GET", endpoint)
       resp.raise_for_status()
       return json.dumps(resp.json(), indent=2)
    except httpx.HTTPStatusError as e:
       return ChartError(
           f"HTTP {e.response.status_code} getting chart data",
           status_code=e.response.status_code,
           details=e.response.text,
       ).to_json()
    except Exception as e:
       return ChartError(f"Unexpected error getting chart data: {e}", details=str(e)).to_json()


async def get_chart_type_schema(
    manager: ConnectionManager,
    server_id: str,
    chart_type: str
) -> str:
    ctx = manager.get_context(server_id)
    if not ctx:
       return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    try:
        result = await impl_superset_api(
            manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
        )
        return ChartTypeSchema(chart_type=chart_type, schema_data={"raw": result}).model_dump_json(indent=2)
    except Exception as e:
        return ChartError(f"Unexpected error getting chart type schema: {e}", details=str(e)).to_json()


async def get_all_chart_schemas(manager: ConnectionManager, server_id: str) -> str:
    """
    Dynamically discovers ALL chart types from Superset API,
    fetches each schema, and returns a consolidated Markdown reference.
    Cached for 24 hours to avoid repeated API calls.
    """
    import asyncio

    async def _fetch_schema(chart_type: str) -> Optional[Dict[str, Any]]:
        try:
            result = await impl_superset_api(
                manager, server_id, "GET", f"/api/v1/chart/schemas/{chart_type}/"
            )
            return {"type": chart_type, "schema": json.loads(result)}
        except Exception:
            return None

    def _parse_schema(schema: Dict[str, Any]) -> Dict[str, Any]:
        properties = schema.get("properties", {})
        parsed_required = []

        # Check top-level "required" array
        if "required" in schema and isinstance(schema["required"], list):
            parsed_required = list(schema["required"])

        metric_fields = []
        groupby_fields = []
        other_fields = []

        for field_name, field_info in properties.items():
            if not isinstance(field_info, dict):
                other_fields.append(f"**{field_name}** (unknown)")
                continue
            field_type = str(field_info.get("type", "unknown"))
            description = field_info.get("description", "") or field_info.get("title", "")
            name_lower = field_name.lower()

            if any(kw in name_lower for kw in ["metric", "aggregate"]):
                metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif any(kw in name_lower for kw in ["group", "series", "dimension", "category", "x_axis", "y_", "slice"]):
                groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
            elif name_lower not in ("datasource", "viz_type", "slice_name", "description", "id"):
                other_fields.append(f"**{field_name}** ({field_type}) - {description}")

        # Check form_data if present
        form_data = schema.get("form_data", {})
        if isinstance(form_data, dict):
            fd_props = form_data.get("properties", {})
            fd_required = form_data.get("required", [])
            if isinstance(fd_required, list):
                parsed_required.extend(fd_required)
            for field_name, field_info in fd_props.items():
                if not isinstance(field_info, dict):
                    continue
                field_type = str(field_info.get("type", "unknown"))
                description = field_info.get("description", "") or field_info.get("title", "")
                name_lower = field_name.lower()
                if any(kw in name_lower for kw in ["metric", "aggregate"]):
                    metric_fields.append(f"**{field_name}** ({field_type}) - {description}")
                elif any(kw in name_lower for kw in ["group", "series", "dimension", "x_", "y_"]):
                    groupby_fields.append(f"**{field_name}** ({field_type}) - {description}")
                elif name_lower not in ("datasource", "viz_type", "slice_name", "description"):
                    other_fields.append(f"**{field_name}** ({field_type}) - {description}")

        return {
            "required": list(set(parsed_required)),
            "metric_fields": metric_fields,
            "groupby_fields": groupby_fields,
            "other_fields": other_fields,
        }

    def _build_markdown(all_schemas: List[Dict[str, Any]], cache_key: str) -> str:
        lines = [
            "# Superset Chart Types - Complete Reference",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
            f"Source: Superset API ({cache_key})",
            "",
            "---",
            "",
            f"**Total chart types available: {len(all_schemas)}**",
            "",
            "## Quick Reference",
            "",
            "| # | Chart Type | Required Fields | Metric Fields | GroupBy Fields |",
            "|---|-----------|----------------|---------------|----------------|",
        ]

        for idx, item in enumerate(all_schemas, 1):
            chart_type = item["type"]
            parsed = item["parsed"]
            required_str = ", ".join(parsed["required"][:5]) if parsed["required"] else "See details"
            metric_count = len(parsed["metric_fields"])
            groupby_count = len(parsed["groupby_fields"])
            lines.append(f"| {idx} | `{chart_type}` | {required_str} | {metric_count} | {groupby_count} |")

        lines.extend(["", "---", "", "## Detailed Schemas", "", ""])

        for item in all_schemas:
            chart_type = item["type"]
            parsed = item["parsed"]
            raw = item.get("raw_schema", {})

            lines.append(f"### `{chart_type}`")
            lines.append("")

            if parsed["required"]:
                lines.append("**Required fields:**")
                for field in parsed["required"]:
                    lines.append(f"- `{field}`")
                lines.append("")

            if parsed["metric_fields"]:
                lines.append("**Metric fields:**")
                for f in parsed["metric_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["metric_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['metric_fields']) - 10} more")
                lines.append("")

            if parsed["groupby_fields"]:
                lines.append("**GroupBy/Dimension fields:**")
                for f in parsed["groupby_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["groupby_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['groupby_fields']) - 10} more")
                lines.append("")

            if parsed["other_fields"]:
                lines.append("**Other fields:**")
                for f in parsed["other_fields"][:10]:
                    lines.append(f"- {f}")
                if len(parsed["other_fields"]) > 10:
                    lines.append(f"- ... and {len(parsed['other_fields']) - 10} more")
                lines.append("")

            form_data = raw.get("form_data", {})
            if isinstance(form_data, dict) and form_data:
                lines.append("**Form data properties (top 15):**")
                fd_props = form_data.get("properties", {})
                for field_name, field_info in list(fd_props.items())[:15]:
                    if isinstance(field_info, dict):
                        field_type = str(field_info.get("type", "unknown"))
                        desc = field_info.get("description", "") or field_info.get("title", "")
                        lines.append(f"- `{field_name}`: {field_type} - {desc}")
                if len(fd_props) > 15:
                    lines.append(f"- ... and {len(fd_props) - 15} more")
                lines.append("")

            lines.append("---")
            lines.append("")

        return "\n".join(lines)

    # --- Main logic ---
    ctx = manager.get_context(server_id)
    if not ctx:
        return ChartError(f"Server '{server_id}' not found.", status_code=404).to_json()

    # Check cache
    if os.path.isfile(CACHE_FILE):
        try:
            file_age = time.time() - os.path.getmtime(CACHE_FILE)
            if file_age < CACHE_TTL_SECONDS:
                with open(CACHE_FILE, "r") as f:
                    cached = json.load(f)
                return cached.get("markdown", json.dumps(cached, indent=2))
        except (json.JSONDecodeError, OSError):
            pass

    # Fetch chart API info to discover all chart types
    try:
        info_raw = await impl_superset_api(manager, server_id, "GET", "/api/v1/chart/_info")
        info_data = json.loads(info_raw)
    except Exception as e:
        return ChartError(f"Failed to fetch chart API info: {e}", details=str(e)).to_json()

    # Extract chart type names from _info response
    chart_types = []
    properties = info_data.get("result", {}).get("properties", {})

    if isinstance(properties, dict):
        # Check form_data.properties.viz_type.enum
        fd = properties.get("form_data", {})
        if isinstance(fd, dict):
            fd_props = fd.get("properties", {})
            viz_type = fd_props.get("viz_type", {})
            if isinstance(viz_type, dict):
                enum_vals = viz_type.get("enum", [])
                if enum_vals:
                    chart_types = [str(v) for v in enum_vals]

        # Check form_data.viz_type if form_data is a top-level property
        if not chart_types:
            form_data_prop = properties.get("form_data", {})
            if isinstance(form_data_prop, dict):
                fd_viz = form_data_prop.get("viz_type", {})
                if isinstance(fd_viz, dict):
                    enum_vals = fd_viz.get("enum", [])
                    if enum_vals:
                        chart_types = [str(v) for v in enum_vals]

        # Try properties.chart_types
        if not chart_types:
            ct = properties.get("chart_types", [])
            if isinstance(ct, list) and ct:
                chart_types = [str(c) for c in ct]

        # Try any property with an enum array
        if not chart_types:
            for key, val in properties.items():
                if isinstance(val, dict) and "enum" in val:
                    enum_vals = val.get("enum", [])
                    if isinstance(enum_vals, list) and len(enum_vals) > 2:
                        chart_types = [str(v) for v in enum_vals]
                        break

    if not chart_types:
        chart_types = list(TYPE_MAP.values())
        chart_types = list(set(chart_types))
        chart_types.sort()

    # Fetch schemas for all chart types (parallel)
    tasks = [_fetch_schema(ct) for ct in chart_types]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # Process results
    all_schemas = []
    for result in results:
        if isinstance(result, Exception):
            continue
        if result is None:
            continue
        try:
            parsed = _parse_schema(result["schema"])
            all_schemas.append({
                "type": result["type"],
                "parsed": parsed,
                "raw_schema": result["schema"],
            })
        except Exception:
            all_schemas.append({
                "type": result["type"],
                "parsed": {"required": [], "metric_fields": [], "groupby_fields": [], "other_fields": ["Schema parsing failed"]},
                "raw_schema": {},
            })

    all_schemas.sort(key=lambda x: x["type"])

    cache_key = f"Superset {info_data.get('result', {}).get('version', 'unknown')}"
    markdown = _build_markdown(all_schemas, cache_key)

    # Write cache
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(CACHE_FILE, "w") as f:
            json.dump({
                "cache_key": cache_key,
                "generated_at": time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime()),
                "total_types": len(all_schemas),
                "chart_types": [s["type"] for s in all_schemas],
                "markdown": markdown,
            }, f, indent=2)
    except OSError:
        pass

    return markdown
