import json
import asyncio
import logging
from typing import Union, Optional, Dict, Any, Tuple
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.models import TRANSFER_STRATEGY, RESOURCE_ENDPOINTS
from modules.SupersetModule.api_client import ensure_auth, execute_request
from modules.SupersetModule.tools.resources import impl_get_resource, impl_list_resources
from modules.SupersetModule.tools.datasets import create_dataset
from modules.SupersetModule.tools.charts import create_chart
from modules.SupersetModule.tools.sqllab import sqllab_execute_query, sqllab_get_query_results

logger = logging.getLogger(__name__)

NEED_INPUT_PREFIX = "NEED_INPUT:"

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
        
        if strategy == "export_import":
            q_param = json.dumps([item_id])
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            export_url = f"{endpoint_base}/export/"
            
            logger.info(f"Exporting {resource_type} {item_id} from {source_server_id}...")
            export_resp = await execute_request(source_ctx, "GET", export_url, params={"q": q_param})
            
            if export_resp.status_code != 200:
                return f"Export failed: {export_resp.status_code} - {export_resp.text}"
            
            import_url = f"{endpoint_base}/import/"
            file_name = f"export_{resource_type}_{item_id}.zip"
            
            files = {'formData': (file_name, export_resp.content, 'application/zip')}
            data = {'overwrite': 'true', 'passwords': '{}'}
            
            logger.info(f"Importing to {target_server_id}...")
            import_resp = await execute_request(target_ctx, "POST", import_url, files=files, data=data)
            
            if import_resp.status_code not in [200, 201]:
                return f"Import failed: {import_resp.status_code} - {import_resp.text}"
            
            return f"Successfully transferred {resource_type} {item_id}."

        elif strategy == "json_copy":
            endpoint_base = RESOURCE_ENDPOINTS.get(resource_type, f"/api/v1/{resource_type}")
            
            detail_url = f"{endpoint_base}/{item_id}"
            get_resp = await execute_request(source_ctx, "GET", detail_url)
            if get_resp.status_code != 200:
                return f"Failed to get item from source: {get_resp.status_code}"
            
            item_data = get_resp.json().get("result")
            if not item_data:
                return "Source item data not found in response."

            params_to_remove = ['id', 'created_by', 'changed_by', 'created_on', 'changed_on', 'owners']
            payload = {k: v for k, v in item_data.items() if k not in params_to_remove}
            
            post_url = f"{endpoint_base}/"
            create_resp = await execute_request(target_ctx, "POST", post_url, json=payload)
            
            if create_resp.status_code not in [200, 201]:
                return f"Failed to create on target: {create_resp.status_code} - {create_resp.text}"
            
            return f"Successfully transferred {resource_type} {item_id} (created new ID)."

        else:
            return f"Unknown transfer strategy for {resource_type}"

    except Exception as e:
        return f"Transfer error: {e}"


def _need_input(resource_type: str, source_id: Any, name: str, available: list) -> str:
    payload = {
        "type": resource_type,
        "source_id": source_id,
        "name": name,
        "available": available
    }
    return f"{NEED_INPUT_PREFIX}{json.dumps(payload)}"


def _parse_json_result(result_str: str) -> Optional[Dict]:
    try:
        return json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return None


async def _resolve_target_database(
    manager: ConnectionManager,
    source_db_id: int,
    source_db_name: str,
    target_server_id: str,
    db_mappings: Dict[int, int]
) -> Tuple[Optional[int], Optional[str]]:
    if source_db_id in db_mappings:
        return db_mappings[source_db_id], None

    dbs_str = await impl_list_resources(manager, target_server_id, "database")
    dbs_data = _parse_json_result(dbs_str)
    if not dbs_data:
        return None, f"Could not list databases on target: {dbs_str}"

    dbs = dbs_data.get("result", [])
    if not isinstance(dbs, list):
        return None, f"Unexpected database list format: {dbs_data}"

    for db in dbs:
        if db.get("database_name", "").lower() == source_db_name.lower():
            return db["id"], None

    available_dbs = [{"id": db["id"], "name": db.get("database_name", "")} for db in dbs if "id" in db]
    return None, _need_input("database", source_db_id, source_db_name, available_dbs)


async def _check_table_exists(
    manager: ConnectionManager,
    target_server_id: str,
    target_db_id: int,
    schema: Optional[str],
    table_name: str
) -> bool:
    db_detail_str = await impl_get_resource(manager, target_server_id, "database", target_db_id)
    db_detail = _parse_json_result(db_detail_str)
    if not db_detail:
        return False

    engine = db_detail.get("result", {}).get("backend", "")

    if engine == "postgresql":
        schema_filter = schema or "public"
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_filter}' AND table_name = '{table_name}' AND table_type = 'BASE TABLE'"
    elif engine == "mysql":
        schema_filter = schema or db_detail.get("result", {}).get("database_name")
        query = f"SELECT table_name FROM information_schema.tables WHERE table_schema = '{schema_filter}' AND table_name = '{table_name}' AND table_type = 'BASE TABLE'"
    elif engine == "mssql":
        schema_filter = schema or "dbo"
        query = f"SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA = '{schema_filter}' AND TABLE_NAME = '{table_name}' AND TABLE_TYPE = 'BASE TABLE'"
    else:
        query = f"SELECT * FROM {schema + '.' if schema else ''}{table_name} LIMIT 1"

    res = await sqllab_execute_query(manager, target_server_id, target_db_id, query, schema=schema)
    res_data = _parse_json_result(res)
    if not res_data:
        return False

    client_id = res_data.get("result", {}).get("query", {}).get("client_id")
    if not client_id:
        return False

    await asyncio.sleep(1)
    results = await sqllab_get_query_results(manager, target_server_id, client_id)
    results_data = _parse_json_result(results)
    if not results_data:
        return False

    data = results_data.get("data", [])
    return len(data) > 0


async def _resolve_dataset(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    source_ds_id: int,
    db_mappings: Dict[int, int],
    table_mappings: Dict[str, str]
) -> Tuple[Optional[int], Optional[str], Optional[str]]:
    ds_str = await impl_get_resource(manager, source_server_id, "dataset", source_ds_id)
    ds_data = _parse_json_result(ds_str)
    if not ds_data:
        return None, None, f"Could not get dataset {source_ds_id} from source: {ds_str}"

    ds_result = ds_data.get("result", {})
    table_name = ds_result.get("table_name", "")
    schema = ds_result.get("schema")
    sql_expression = ds_result.get("sql")
    source_db_id = ds_result.get("database", {}).get("id")

    if not source_db_id:
        db_info = ds_result.get("database", {})
        return None, None, f"Dataset {source_ds_id} has no database info: {db_info}"

    db_str = await impl_get_resource(manager, source_server_id, "database", source_db_id)
    db_data = _parse_json_result(db_str)
    if not db_data:
        return None, None, f"Could not get database {source_db_id} from source: {db_str}"

    db_result = db_data.get("result", {})
    source_db_name = db_result.get("database_name", "")

    target_db_id, err = await _resolve_target_database(
        manager, source_db_id, source_db_name, target_server_id, db_mappings
    )
    if err:
        return None, None, err

    mapped_table = table_mappings.get(table_name, table_name)

    table_exists = await _check_table_exists(manager, target_server_id, target_db_id, schema, mapped_table)
    if not table_exists:
        return None, None, _need_input("table", table_name, mapped_table, [])

    dataset_result_str = await create_dataset(
        manager,
        target_server_id,
        table_name=mapped_table,
        database_id=target_db_id,
        schema=schema,
        sql_expression=sql_expression
    )
    if "Error" in dataset_result_str:
        return None, None, f"Failed to create dataset '{mapped_table}' on target: {dataset_result_str}"

    dataset_result = _parse_json_result(dataset_result_str)
    if not dataset_result:
        return None, None, f"Could not parse dataset creation result: {dataset_result_str}"

    new_ds_id = dataset_result.get("id")
    if not new_ds_id:
        return None, None, f"Dataset created but no ID returned: {dataset_result_str}"

    return new_ds_id, ds_result.get("datasource_type", "table"), None


async def _recreate_chart(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    source_chart_id: int,
    ds_mapping: Dict[int, Tuple[int, str]]
) -> Tuple[Optional[int], Optional[str]]:
    chart_str = await impl_get_resource(manager, source_server_id, "chart", source_chart_id)
    chart_data = _parse_json_result(chart_str)
    if not chart_data:
        return None, f"Could not get chart {source_chart_id} from source: {chart_str}"

    chart_result = chart_data.get("result", {})
    slice_name = chart_result.get("slice_name", f"Chart {source_chart_id}")
    viz_type = chart_result.get("viz_type", "table")
    old_ds_id = chart_result.get("datasource_id")
    datasource_type = chart_result.get("datasource_type", "table")
    params_raw = chart_result.get("params", "{}")
    description = chart_result.get("description")

    if old_ds_id not in ds_mapping:
        return None, f"Chart {source_chart_id} references datasource {old_ds_id} which was not transferred"

    new_ds_id, new_ds_type = ds_mapping[old_ds_id]

    if isinstance(params_raw, dict):
        params_json = json.dumps(params_raw)
    else:
        params_json = params_raw

    result_str = await create_chart(
        manager,
        target_server_id,
        slice_name=slice_name,
        viz_type=viz_type,
        datasource_id=new_ds_id,
        datasource_type=new_ds_type or datasource_type,
        params=params_json,
        description=description
    )

    if "Error" in result_str:
        return None, f"Failed to create chart '{slice_name}' on target: {result_str}"

    result_data = _parse_json_result(result_str)
    if not result_data:
        return None, f"Could not parse chart creation result: {result_str}"

    new_chart_id = result_data.get("id")
    if not new_chart_id:
        return None, f"Chart created but no ID returned: {result_str}"

    return new_chart_id, None


async def transfer_dashboard(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int,
    db_mappings: Optional[str] = None,
    table_mappings: Optional[str] = None
) -> str:
    source_ctx = manager.get_context(source_server_id)
    target_ctx = manager.get_context(target_server_id)

    if not source_ctx or not target_ctx:
        return "Error: Source or target server not found."

    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)
    except Exception as e:
        return f"Authentication failed: {e}"

    parsed_db_mappings: Dict[int, int] = {}
    if db_mappings:
        try:
            raw = json.loads(db_mappings)
            parsed_db_mappings = {int(k): int(v) for k, v in raw.items()}
        except (json.JSONDecodeError, ValueError) as e:
            return f"Invalid db_mappings JSON: {e}"

    parsed_table_mappings: Dict[str, str] = {}
    if table_mappings:
        try:
            parsed_table_mappings = json.loads(table_mappings)
        except json.JSONDecodeError as e:
            return f"Invalid table_mappings JSON: {e}"

    logger.info(f"Fetching source dashboard {dashboard_id}...")
    dash_str = await impl_get_resource(manager, source_server_id, "dashboard", dashboard_id)
    dash_data = _parse_json_result(dash_str)
    if not dash_data:
        return f"Could not get dashboard {dashboard_id} from source: {dash_str}"

    dash_result = dash_data.get("result", {})
    source_charts = dash_result.get("charts", [])
    if not source_charts:
        return f"No charts found in dashboard {dashboard_id}"

    source_chart_ids = []
    for c in source_charts:
        cid = c.get("id")
        if cid:
            source_chart_ids.append(cid)

    logger.info(f"Found {len(source_chart_ids)} charts in source dashboard")

    unique_ds_ids: Dict[int, str] = {}
    for cid in source_chart_ids:
        chart_str = await impl_get_resource(manager, source_server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if chart_data:
            ds_id = chart_data.get("result", {}).get("datasource_id")
            if ds_id:
                unique_ds_ids[ds_id] = chart_data["result"].get("datasource_type", "table")

    if not unique_ds_ids:
        return "No datasources found in source charts"

    logger.info(f"Phase 1: Resolving {len(unique_ds_ids)} unique datasources...")
    ds_mapping: Dict[int, Tuple[int, str]] = {}
    for old_ds_id, ds_type in unique_ds_ids.items():
        new_ds_id, resolved_ds_type, err = await _resolve_dataset(
            manager, source_server_id, target_server_id,
            old_ds_id, parsed_db_mappings, parsed_table_mappings
        )
        if err:
            if err.startswith(NEED_INPUT_PREFIX):
                return err
            return f"Failed to resolve datasource {old_ds_id}: {err}"
        ds_mapping[old_ds_id] = (new_ds_id, resolved_ds_type or ds_type)
        logger.info(f"  Datasource {old_ds_id} -> {new_ds_id}")

    logger.info(f"Phase 2: Recreating {len(source_chart_ids)} charts...")
    chart_id_mapping: Dict[int, int] = {}
    for cid in source_chart_ids:
        new_cid, err = await _recreate_chart(
            manager, source_server_id, target_server_id,
            cid, ds_mapping
        )
        if err:
            return f"Failed to recreate chart {cid}: {err}"
        chart_id_mapping[cid] = new_cid
        logger.info(f"  Chart {cid} -> {new_cid}")

    from modules.SupersetModule.tools.dashboards import create_dashboard, bulk_link_charts
    logger.info(f"Phase 3: Creating dashboard...")
    dashboard_title = dash_result.get("dashboard_title", f"Transferred Dashboard {dashboard_id}")
    position_json_raw = dash_result.get("position_json", "{}")
    json_metadata_raw = dash_result.get("json_metadata", "{}")
    slug = dash_result.get("slug")
    published = dash_result.get("published", False)

    if isinstance(position_json_raw, dict):
        position_json = position_json_raw
    else:
        try:
            position_json = json.loads(position_json_raw)
        except (json.JSONDecodeError, TypeError):
            position_json = {}

    position_json_updated = json.dumps(_remap_chart_ids_in_position_json(position_json, chart_id_mapping))

    if isinstance(json_metadata_raw, dict):
        json_metadata = json_metadata_raw
    else:
        try:
            json_metadata = json.loads(json_metadata_raw)
        except (json.JSONDecodeError, TypeError):
            json_metadata = {}

    json_metadata_updated = json.dumps(json_metadata)

    new_dash_str = await create_dashboard(
        manager, target_server_id,
        dashboard_title=dashboard_title,
        position_json=position_json_updated,
        slug=slug,
        json_metadata=json_metadata_updated,
        published=published
    )

    if "Error" in new_dash_str:
        return f"Failed to create dashboard: {new_dash_str}"

    new_dash_data = _parse_json_result(new_dash_str)
    if not new_dash_data:
        return f"Could not parse dashboard creation result: {new_dash_str}"

    new_dash_id = new_dash_data.get("id")
    if not new_dash_id:
        return f"Dashboard created but no ID returned: {new_dash_str}"

    new_chart_ids = list(chart_id_mapping.values())
    link_result = await bulk_link_charts(manager, target_server_id, new_dash_id, new_chart_ids)

    summary = {
        "message": "Dashboard transferred successfully",
        "source_dashboard_id": dashboard_id,
        "target_dashboard_id": new_dash_id,
        "datasource_mapping": {str(k): v[0] for k, v in ds_mapping.items()},
        "chart_mapping": {str(k): v for k, v in chart_id_mapping.items()},
        "link_result": link_result
    }
    return json.dumps(summary, indent=2)


def _remap_chart_ids_in_position_json(position_json: Dict, chart_id_mapping: Dict[int, int]) -> Dict:
    if not isinstance(position_json, dict):
        return position_json

    updated = {}
    for key, value in position_json.items():
        if isinstance(value, dict):
            child_type = value.get("type", "")
            if child_type == "CHART":
                old_chart_id = value.get("meta", {}).get("chartId") or value.get("id")
                if old_chart_id and old_chart_id in chart_id_mapping:
                    new_id = chart_id_mapping[old_chart_id]
                    new_value = dict(value)
                    new_value["id"] = new_id
                    if "meta" in new_value:
                        new_meta = dict(new_value["meta"])
                        new_meta["chartId"] = new_id
                        new_meta["id"] = new_id
                        new_value["meta"] = new_meta
                    updated[key] = new_value
                    continue
            updated[key] = _remap_chart_ids_in_position_json(value, chart_id_mapping)
        elif isinstance(value, list):
            updated[key] = [
                _remap_chart_ids_in_position_json(item, chart_id_mapping) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            updated[key] = value

    return updated
