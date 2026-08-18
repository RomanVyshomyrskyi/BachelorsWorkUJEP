"""
Dashboard and chart transfer tools between Superset servers.

Core functions for the transfer pipeline.
"""

import json
from typing import Union, Optional, Dict, Any
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import TRANSFER_STRATEGY, RESOURCE_ENDPOINTS
from modules.SupersetModule.api_client import ensure_auth, execute_request
from modules.SupersetModule.exceptions import TransferError
from modules.log_utils import LogCollector

log = LogCollector(__name__)
NEED_INPUT_PREFIX = "NEED_INPUT:"


async def impl_transfer_item(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    resource_type: str,
    item_id: Union[int, str]
) -> str:
    """Transfer a single resource item between Superset servers.

    Selects the transfer strategy from ``TRANSFER_STRATEGY`` based on
    resource type: ``export_import`` for charts/dashboards/databases/datasets,
    ``json_copy`` for other types. Handles authentication, export, and import
    phases for both strategies.
        For ``export_import``: GETs the export ZIP from the source server
        (with query param ``q=[item_id]``), then POSTs it as multipart/form-data
        to the target server's import endpoint with ``overwrite=true``.
        For ``json_copy``: GETs the item detail from the source, strips
        read-only metadata fields (id, created_by, etc.), and POSTs the
        sanitized payload to create a clone on the target.

    Args:
        manager: ConnectionManager with source and target server configs.
        source_server_id: Source Superset server ID.
        target_server_id: Target Superset server ID.
        resource_type: Superset resource type (e.g. "chart", "dashboard").
        item_id: Integer or string ID of the resource to transfer.

    Returns:
        JSON string with a success message or a TransferError JSON on failure.

    Examples:
        result = await impl_transfer_item(
            manager, source_server_id="source", target_server_id="target",
            resource_type="chart", item_id=123
        )
        # Returns JSON with success message or TransferError details.
    """
    source_ctx = manager.get_context(source_server_id)
    target_ctx = manager.get_context(target_server_id)

    if not source_ctx or not target_ctx:
        return log_impl.collect(TransferError("Source or target server not found.", status_code=404).to_json())

    strategy = TRANSFER_STRATEGY.get(resource_type, "json_copy")

    log_impl = LogCollector(__name__)

    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)

        if strategy == "export_import":
            q_param = json.dumps([item_id])
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            export_url = f"{endpoint_base}/export/"

            log_impl.info(f"Exporting {resource_type} {item_id} from {source_server_id}...")
            export_resp = await execute_request(source_ctx, "GET", export_url, params={"q": q_param})

            if export_resp.status_code != 200:
                return log_impl.collect(TransferError(
                    f"Export failed: HTTP {export_resp.status_code}",
                    status_code=export_resp.status_code,
                    details=export_resp.text,
                ).to_json())

            import_url = f"{endpoint_base}/import/"
            file_name = f"export_{resource_type}_{item_id}.zip"

            files = {'formData': (file_name, export_resp.content, 'application/zip')}
            data = {'overwrite': 'true', 'passwords': '{}'}

            log_impl.info(f"Importing to {target_server_id}...")
            import_resp = await execute_request(target_ctx, "POST", import_url, files=files, data=data)

            if import_resp.status_code not in [200, 201]:
                return log_impl.collect(TransferError(
                    f"Import failed: HTTP {import_resp.status_code}",
                    status_code=import_resp.status_code,
                    details=import_resp.text,
                ).to_json())

            return log_impl.collect(json.dumps({"message": f"Successfully transferred {resource_type} {item_id}."}))

        elif strategy == "json_copy":
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")

            detail_url = f"{endpoint_base}/{item_id}"
            get_resp = await execute_request(source_ctx, "GET", detail_url)
            if get_resp.status_code != 200:
                return log_impl.collect(TransferError(
                    f"Failed to get item from source: HTTP {get_resp.status_code}",
                    status_code=get_resp.status_code,
                ).to_json())

            item_data = get_resp.json().get("result")
            if not item_data:
                return log_impl.collect(TransferError("Source item data not found in response.").to_json())

            params_to_remove = ['id', 'created_by', 'changed_by', 'created_on', 'changed_on', 'owners']
            payload = {k: v for k, v in item_data.items() if k not in params_to_remove}

            post_url = f"{endpoint_base}/"
            create_resp = await execute_request(target_ctx, "POST", post_url, json=payload)

            if create_resp.status_code not in [200, 201]:
                return log_impl.collect(TransferError(
                    f"Failed to create on target: HTTP {create_resp.status_code}",
                    status_code=create_resp.status_code,
                    details=create_resp.text,
                ).to_json())

            return log_impl.collect(json.dumps({"message": f"Successfully transferred {resource_type} {item_id} (created new ID)."}))

        else:
            return log_impl.collect(TransferError(f"Unknown transfer strategy for {resource_type}").to_json())

    except Exception as e:
        return log_impl.collect(TransferError(f"Transfer error: {e}", details=str(e)).to_json())


def _need_input(resource_type: str, source_id: Any, name: str, available: list) -> str:
    """Build a ``NEED_INPUT`` prefix message requesting user intervention.

    Used when automatic resolution fails (e.g., no matching database or table
    found on the target server). The caller can parse the JSON payload after
    the ``NEED_INPUT:`` prefix to present options to the user.

    Args:
        resource_type: Type of resource needing input (e.g. "database").
        source_id: ID of the resource on the source server.
        name: Human-readable name of the resource.
        available: List of available options on the target server.

    Returns:
        String with ``NEED_INPUT:`` prefix followed by a JSON payload
        containing type, source_id, name, and available options.
    """
    payload = {
        "type": resource_type,
        "source_id": source_id,
        "name": name,
        "available": available
    }
    return f"{NEED_INPUT_PREFIX}{json.dumps(payload)}"


def _parse_json_result(result_str: str) -> Optional[Dict]:
    """Parse a JSON string result safely, returning None on failure.

    Args:
        result_str: Raw JSON string to parse.

    Returns:
        Parsed dict on success, None if the string is not valid JSON.
    """
    try:
        return json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return None
