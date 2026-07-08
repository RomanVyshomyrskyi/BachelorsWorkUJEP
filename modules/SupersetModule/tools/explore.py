import json
import httpx
from typing import Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import execute_request


async def generate_explore_link(
    manager: ConnectionManager,
    server_id: str,
    dataset_id: int,
    config: Optional[str] = None
) -> str:
    """Generate an interactive explore URL for ad-hoc data exploration.
    
    Creates a URL that opens Superset's Explore view with pre-configured
    chart settings based on the dataset and optional chart configuration.
    
    This is the preferred tool for exploration - it does NOT create a
    permanent chart. Use generate_chart only when the user wants to save.
    
    Args:
        server_id: The ID of the configured Superset server.
        dataset_id: The ID of the dataset to explore.
        config: Optional JSON string of chart configuration (viz_type, metrics, etc.).
    Returns:
        JSON string containing the explore link URL.
    """
    ctx = manager.get_context(server_id)
    if not ctx:
        return f"Error: Server '{server_id}' not found."
    
    try:
        # Parse config if provided
        chart_config = {}
        if config:
            try:
                chart_config = json.loads(config)
            except json.JSONDecodeError:
                return f"Error: 'config' is not a valid JSON string."
        
        # Build form_data for the explore link
        form_data: Dict[str, Any] = {
            "datasource_id": dataset_id,
            "datasource_type": "table",
        }
        form_data.update(chart_config)
        
        # Build explore URL
        base_url = ctx.config.base_url.rstrip("/")
        explore_url = f"{base_url}/explore/?form_data={json.dumps(form_data)}"
        
        return json.dumps({
            "url": explore_url,
            "dataset_id": dataset_id,
            "config": chart_config,
            "note": "This is an exploration link. It does NOT create a permanent chart."
        }, indent=2)
        
    except httpx.HTTPStatusError as e:
        return f"Error generating explore link: {e.response.status_code} - {e.response.text}"
    except Exception as e:
        return f"An unexpected error occurred while generating the explore link: {e}"
