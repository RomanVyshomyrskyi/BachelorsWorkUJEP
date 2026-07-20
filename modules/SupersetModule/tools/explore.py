import json
import httpx
import time
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request
from modules.SupersetModule.exceptions import ExploreError
from modules.metrics import get_metrics


async def generate_explore_link(
     manager: ConnectionManager,
     server_id: str,
     dataset_id: int,
     config: Optional[str] = None
 ) -> str:
     ctx = manager.get_context(server_id)
     if not ctx:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_explore_link", status="error").inc()
         mc.record_error(tool="superset_generate_explore_link", error_message=f"Server '{server_id}' not found.")
         return ExploreError(f"Server '{server_id}' not found.", status_code=404).to_json()

     start_time = time.monotonic()
     try:
         chart_config = {}
         if config:
             try:
                 chart_config = json.loads(config)
             except json.JSONDecodeError:
                 mc = get_metrics()
                 mc.tool_calls.labels(tool="superset_generate_explore_link", status="error").inc()
                 mc.record_error(tool="superset_generate_explore_link", error_message="Invalid JSON in config")
                 return ExploreError("'config' is not a valid JSON string.", details=config).to_json()

         form_data: Dict[str, Any] = {
             "datasource_id": dataset_id,
             "datasource_type": "table",
         }
         form_data.update(chart_config)

         base_url = ctx.config.base_url.rstrip("/")
         explore_url = f"{base_url}/explore/?form_data={json.dumps(form_data)}"

         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_explore_link", status="success").inc()
         mc.tool_duration.labels(tool="superset_generate_explore_link").observe(time.monotonic() - start_time)
         mc.charts_generated.labels(chart_type="explore").inc()
         return json.dumps({
             "url": explore_url,
             "dataset_id": dataset_id,
             "config": chart_config,
             "note": "This is an exploration link. It does NOT create a permanent chart."
         }, indent=2)

     except httpx.HTTPStatusError as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_explore_link", status="error").inc()
         mc.record_error(tool="superset_generate_explore_link", error_message=f"HTTP {e.response.status_code} generating explore link", status_code=e.response.status_code)
         return ExploreError(
             f"HTTP {e.response.status_code} generating explore link",
             status_code=e.response.status_code,
             details=e.response.text,
         ).to_json()
     except Exception as e:
         mc = get_metrics()
         mc.tool_calls.labels(tool="superset_generate_explore_link", status="error").inc()
         mc.record_error(tool="superset_generate_explore_link", error_message=str(e))
         return ExploreError(f"Unexpected error generating explore link: {e}", details=str(e)).to_json()
