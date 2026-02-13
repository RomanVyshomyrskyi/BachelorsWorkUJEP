import json
from typing import Union
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import TRANSFER_STRATEGY, RESOURCE_ENDPOINTS
from modules.SupersetModule.api_client import ensure_auth, execute_request
import logging

logger = logging.getLogger(__name__)

async def impl_transfer_item(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    resource_type: str,
    item_id: Union[int, str]
) -> str:
    source_ctx = manager.get_context(source_server_id)
    target_ctx = manager.get_context(target_server_id)

    if not source_ctx or not target_ctx:
        return "Error: Server not found."

    strategy = TRANSFER_STRATEGY.get(resource_type, "json_copy")
    
    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)
        
        # Strategy: Export/Import (ZIP)
        if strategy == "export_import":
            # Export
            # Most export endpoints take `q=[id]`
            q_param = json.dumps([item_id])
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            export_url = f"{endpoint_base}/export/"
            
            logger.info(f"Exporting {resource_type} {item_id} from {source_server_id}...")
            export_resp = await execute_request(source_ctx, "GET", export_url, params={"q": q_param})
            
            if export_resp.status_code != 200:
                return f"Export failed: {export_resp.status_code} - {export_resp.text}"
            
            # Import
            import_url = f"{endpoint_base}/import/"
            file_name = f"export_{resource_type}_{item_id}.zip"
            
            files = {'formData': (file_name, export_resp.content, 'application/zip')}
            data = {'overwrite': 'true', 'passwords': '{}'}
            
            logger.info(f"Importing to {target_server_id}...")
            import_resp = await execute_request(target_ctx, "POST", import_url, files=files, data=data)
            
            if import_resp.status_code not in [200, 201]:
                return f"Import failed: {import_resp.status_code} - {import_resp.text}"
            
            return f"Successfully transferred {resource_type} {item_id}."

        # Strategy: JSON Copy (Get Detail -> Post Create)
        elif strategy == "json_copy":
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            
            # Get Detail
            detail_url = f"{endpoint_base}/{item_id}"
            get_resp = await execute_request(source_ctx, "GET", detail_url)
            if get_resp.status_code != 200:
                return f"Failed to get item from source: {get_resp.status_code}"
            
            item_data = get_resp.json().get("result")
            if not item_data:
                return "Source item data not found in response."

            # Cleanup for Creation
            params_to_remove = ['id', 'created_by', 'changed_by', 'created_on', 'changed_on', 'owners']
            payload = {k: v for k, v in item_data.items() if k not in params_to_remove}
            
            # Post Create
            post_url = f"{endpoint_base}/"
            create_resp = await execute_request(target_ctx, "POST", post_url, json=payload)
            
            if create_resp.status_code not in [200, 201]:
                return f"Failed to create on target: {create_resp.status_code} - {create_resp.text}"
            
            return f"Successfully transferred {resource_type} {item_id} (created new ID)."

        else:
            return f"Unknown transfer strategy for {resource_type}"

    except Exception as e:
        return f"Transfer error: {e}"
