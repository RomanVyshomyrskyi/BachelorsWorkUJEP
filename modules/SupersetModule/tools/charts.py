import json
import httpx
import time
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

    start_time = time.monotonic()
    try:
        actual_viz_type = _resolve_viz_type(viz_type)
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
        else:
            warning = None
        
        errors = validate_chart_params(actual_viz_type, fixed_params)
        validation_errors = format_error_summary(errors) if errors else None
        
        if validation_errors:
            if warning:
                warning = warning + " | " + validation_errors
            else:
                warning = "Validation: " + validation_errors

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

    start_time = time.monotonic()
    try:
        chart_config = json.loads(config) if config else {}

        viz_type = chart_config.get("viz_type", "table")
        actual_viz_type = _resolve_viz_type(viz_type)
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
        else:
            validation_warning = None
        
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
