"""
Dashboard expert info and import readiness check tools.

Provides:
    - get_dashboard_expert_info: Extract dashboard name, tables, datasets, SQL queries
    - check_dashboard_import_ready: Validate if a dashboard can be imported into target server
"""

import json
import re
import time
from typing import Dict, Any, List, Optional, Set
from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.api_client import ensure_auth
from modules.SupersetModule.tools.general import impl_superset_api
from modules.SupersetModule.tools.resources import impl_list_resources, impl_get_resource
from modules.SupersetModule.tools.export_import.export import _extract_chart_ids_from_position_json
from modules.SupersetModule.tools.transfer.core import _parse_json_result
from modules.log_utils import LogCollector
from modules.metrics import get_metrics

log = LogCollector(__name__)


def _extract_sql_from_params(params: Dict[str, Any]) -> List[str]:
    """Extract SQL queries from chart params dict."""
    sqls = []
    if not isinstance(params, dict):
        return sqls

    # Direct sql field
    for key in ("sql", "inline_sql", "query_sql", "table_query"):
        val = params.get(key)
        if isinstance(val, str) and val.strip():
            sqls.append(val.strip())

    # SQL column expressions
    for key in ("columns", "metric", "metrics", "groupby", "where", "having", "order_by"):
        val = params.get(key)
        if isinstance(val, list):
            for item in val:
                if isinstance(item, dict):
                    sql_expr = item.get("expression") or item.get("label") or item.get("sql")
                    if isinstance(sql_expr, str) and sql_expr.strip() and not sql_expr.startswith("_"):
                        # Check if it looks like SQL (contains SQL keywords)
                        sql_keywords = {"SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY",
                                       "SUM(", "COUNT(", "AVG(", "MIN(", "MAX(", "JOIN",
                                       "INNER", "LEFT", "RIGHT", "OUTER", "CASE", "WHEN",
                                       "THEN", "ELSE", "END", "AS ", "DISTINCT"}
                        upper = sql_expr.upper()
                        if any(kw in upper for kw in sql_keywords):
                            sqls.append(sql_expr.strip())
                elif isinstance(item, str):
                    sql_keywords = {"SELECT", "FROM", "WHERE", "GROUP BY", "ORDER BY",
                                   "SUM(", "COUNT(", "AVG(", "MIN(", "MAX(", "JOIN",
                                   "INNER", "LEFT", "RIGHT", "OUTER", "CASE", "WHEN",
                                   "THEN", "ELSE", "END", "AS ", "DISTINCT"}
                    upper = item.upper()
                    if any(kw in upper for kw in sql_keywords) and len(item) > 10:
                        sqls.append(item.strip())

    return sqls


def _extract_tables_from_sql(sql: str) -> List[str]:
    """Extract table names from SQL query."""
    tables = []
    if not sql:
        return tables

    # FROM clause - handle multiple tables
    from_pattern = r'\bFROM\s+([a-zA-Z_][\w.]*)(?:\s+(?:AS\s+)?[a-zA-Z_]\w*)?(?:\s*(?:WHERE|GROUP|ORDER|HAVING|LIMIT|UNION|INTERSECT|EXCEPT|JOIN|LEFT|RIGHT|INNER|OUTER|CROSS|ON|SET|;|$))'
    for match in re.finditer(from_pattern, sql, re.IGNORECASE | re.MULTILINE):
        table = match.group(1)
        # Handle schema.table format
        if '.' in table:
            schema, tbl = table.split('.', 1)
            tables.append({"schema": schema.lower(), "table": tbl.lower()})
        else:
            tables.append({"schema": None, "table": table.lower()})

    # JOIN clause
    join_pattern = r'\bJOIN\s+([a-zA-Z_][\w.]*)(?:\s+(?:AS\s+)?[a-zA-Z_]\w*)?'
    for match in re.finditer(join_pattern, sql, re.IGNORECASE | re.MULTILINE):
        table = match.group(1)
        if '.' in table:
            schema, tbl = table.split('.', 1)
            tables.append({"schema": schema.lower(), "table": tbl.lower()})
        else:
            tables.append({"schema": None, "table": table.lower()})

    # CTE (WITH clause)
    cte_pattern = r'\bWITH\s+([a-zA-Z_]\w*)\s+AS\s*\('
    for match in re.finditer(cte_pattern, sql, re.IGNORECASE):
        cte_name = match.group(1).lower()
        tables.append({"schema": None, "table": f"CTE:{cte_name}"})

    return tables


async def get_dashboard_expert_info(
    manager: ConnectionManager,
    server_id: str,
    dashboard_id: int
) -> str:
    """Get comprehensive info about a dashboard: name, data sources, tables, datasets, SQL.

    This tool extracts all the data lineage information from a dashboard including:
    - Dashboard title and metadata
    - All charts with their viz types
    - All datasets referenced by charts
    - All database tables accessed
    - All SQL queries used in virtual datasets and chart params

    Args:
        server_id: The Superset server ID (as defined in servers.json).
        dashboard_id: The integer ID of the dashboard to analyze.

    Returns:
        JSON string containing structured dashboard info:
        - dashboard: name, id, charts count
        - charts: list with id, name, viz_type, dataset_id, dataset_name, table_refs, sql
        - datasets: list with id, name, type (physical/virtual), database, table_name, sql (if virtual), columns, metrics
        - databases: list with id, name, engine
        - tables: unique list of table references accessed
        - sql_queries: list of all SQL queries found

    Example:
        result = await get_dashboard_expert_info(manager, "production", 42)
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

    # --- Fetch dashboard ---
    dash_str = await impl_get_resource(manager, server_id, "dashboard", dashboard_id)
    dash_data = _parse_json_result(dash_str)
    if not dash_data:
        return log.collect(f"Error: Could not get dashboard {dashboard_id} from {server_id}")

    dash_result = dash_data.get("result", {})
    dashboard_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")
    position_json_raw = dash_result.get("position_json", "{}")
    chart_ids = _extract_chart_ids_from_position_json(position_json_raw)

    if not chart_ids:
        source_charts = dash_result.get("charts", [])
        for c in source_charts:
            if isinstance(c, dict):
                cid = c.get("id")
            elif isinstance(c, (int, str)):
                cid = c
            else:
                continue
            if cid:
                chart_ids.append(int(cid) if isinstance(cid, str) else cid)

    # --- Collect all data ---
    charts_info = []
    datasets_info = []
    databases_info = []
    all_tables: Set[str] = set()
    all_sql_queries: List[str] = []
    unique_datasets: Dict[int, Dict] = {}
    unique_databases: Dict[int, Dict] = {}

    # --- Fetch each chart ---
    for cid in chart_ids:
        chart_str = await impl_get_resource(manager, server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if not chart_data:
            continue

        chart_result = chart_data.get("result", {})
        chart_name = chart_result.get("slice_name", f"Chart {cid}")
        viz_type = chart_result.get("viz_type", "unknown")
        ds_id = chart_result.get("datasource_id")
        ds_type = chart_result.get("datasource_type", "table")

        # Parse params to extract SQL
        params_raw = chart_result.get("params", "{}")
        if isinstance(params_raw, str):
            try:
                params = json.loads(params_raw)
            except json.JSONDecodeError:
                params = {}
        else:
            params = params_raw or {}

        chart_sqls = _extract_sql_from_params(params)
        chart_tables = []

        chart_entry = {
            "id": cid,
            "name": chart_name,
            "viz_type": viz_type,
            "datasource_id": ds_id,
            "datasource_type": ds_type,
            "sql_in_params": chart_sqls
        }

        # Track SQL queries
        for sql in chart_sqls:
            all_sql_queries.append({"chart_id": cid, "chart_name": chart_name, "sql": sql})
            chart_tables.extend(_extract_tables_from_sql(sql))

        # Store chart info
        charts_info.append(chart_entry)

        # --- Fetch dataset if not already fetched ---
        if ds_id and ds_id not in unique_datasets:
            ds_str = await impl_get_resource(manager, server_id, "dataset", ds_id)
            ds_data = _parse_json_result(ds_str)
            if ds_data:
                ds_result = ds_data.get("result", {})
                ds_table_name = ds_result.get("table_name", f"Dataset {ds_id}")

                # Database reference
                db_id = ds_result.get("database")
                if isinstance(db_id, dict):
                    db_id = db_id.get("id")
                if db_id and db_id not in unique_databases:
                    unique_databases[int(db_id)] = {"id": int(db_id), "name": ds_result.get("database", {}).get("database_name", f"DB {db_id}")}

                # Is it a virtual dataset with SQL?
                ds_sql = ds_result.get("sql")
                ds_columns = ds_result.get("columns", [])
                ds_metrics = ds_result.get("metrics", [])

                ds_entry = {
                    "id": ds_result.get("id"),
                    "name": ds_table_name,
                    "type": "virtual" if ds_sql else "physical",
                    "database_id": db_id,
                    "schema": ds_result.get("schema"),
                    "table_name": ds_table_name,
                    "columns": [{"name": c.get("column_name"), "type": c.get("type")} for c in ds_columns] if ds_columns else [],
                    "metrics": [{"name": m.get("metric_name"), "expression": m.get("metric_expression")} for m in ds_metrics] if ds_metrics else []
                }

                if ds_sql:
                    ds_entry["sql"] = ds_sql
                    all_sql_queries.append({"chart_id": ds_id, "chart_name": f"Dataset: {ds_table_name}", "sql": ds_sql})
                    chart_tables.extend(_extract_tables_from_sql(ds_sql))

                    # Extract table refs from SQL
                    for tbl in _extract_tables_from_sql(ds_sql):
                        all_tables.add(json.dumps(tbl))

                unique_datasets[ds_id] = ds_entry
                datasets_info.append(ds_entry)

        # Extract table refs from chart params SQL
        for tbl in chart_tables:
            all_tables.add(json.dumps(tbl))

    # --- Fetch database details ---
    for db_id in unique_databases:
        db_str = await impl_get_resource(manager, server_id, "database", db_id)
        db_data = _parse_json_result(db_str)
        if db_data:
            db_result = db_data.get("result", {})
            unique_databases[db_id]["engine"] = db_result.get("engine")
            unique_databases[db_id]["sqlalchemy_uri"] = db_result.get("sqlalchemy_uri")
            databases_info.append(unique_databases[db_id])

    # --- Build result ---
    result = {
        "dashboard": {
            "id": dashboard_id,
            "name": dashboard_title,
            "chart_count": len(charts_info),
            "chart_ids": chart_ids
        },
        "charts": charts_info,
        "datasets": datasets_info,
        "databases": databases_info,
        "tables": list(all_tables),
        "sql_queries": all_sql_queries,
        "summary": {
            "total_charts": len(charts_info),
            "total_datasets": len(datasets_info),
            "total_databases": len(databases_info),
            "total_tables": len(all_tables),
            "total_sql_queries": len(all_sql_queries)
        }
    }

    mc.tool_calls.labels(tool="get_dashboard_expert_info", status="success").inc()
    mc.tool_duration.labels(tool="get_dashboard_expert_info").observe(time.monotonic() - start_time)

    return json.dumps(result, indent=2, default=str)


async def check_dashboard_import_ready(
    manager: ConnectionManager,
    source_server_id: str,
    target_server_id: str,
    dashboard_id: int
) -> str:
    """Check if a dashboard can be imported into a target Superset server.

    This tool analyzes a dashboard's data dependencies and checks whether all
    required resources exist on the target server. It validates:
    - Databases referenced by datasets exist on target
    - Datasets referenced by charts exist on target (or can be recreated)
    - Chart dependencies are satisfied

    Args:
        source_server_id: The Superset server ID where the dashboard currently exists.
        target_server_id: The Superset server ID to import into.
        dashboard_id: The integer ID of the dashboard to check.

    Returns:
        JSON string with import readiness report:
        - can_import: Boolean indicating if import is possible
        - dashboard: Dashboard name and ID
        - checks: Detailed check results for databases, datasets, charts
        - blockers: List of issues preventing import (empty if can_import=True)
        - recommendations: Suggested actions to make import possible

    Example:
        result = await check_dashboard_import_ready(manager, "production", "staging", 42)
    """
    import time
    mc = get_metrics()
    start_time = time.monotonic()

    # Validate servers exist
    source_ctx = manager.get_context(source_server_id)
    if not source_ctx:
        return log.collect(f"Error: Source server '{source_server_id}' not found.")

    target_ctx = manager.get_context(target_server_id)
    if not target_ctx:
        return log.collect(f"Error: Target server '{target_server_id}' not found.")

    try:
        await ensure_auth(source_ctx)
        await ensure_auth(target_ctx)
    except Exception as e:
        return log.collect(f"Error: Authentication failed: {e}")

    blockers = []
    recommendations = []
    checks = {
        "databases": [],
        "datasets": [],
        "charts": []
    }

    # --- Fetch dashboard ---
    dash_str = await impl_get_resource(manager, source_server_id, "dashboard", dashboard_id)
    dash_data = _parse_json_result(dash_str)
    if not dash_data:
        return log.collect(f"Error: Could not get dashboard {dashboard_id} from {source_server_id}")

    dash_result = dash_data.get("result", {})
    dashboard_title = dash_result.get("dashboard_title", f"Dashboard {dashboard_id}")
    position_json_raw = dash_result.get("position_json", "{}")
    chart_ids = _extract_chart_ids_from_position_json(position_json_raw)

    if not chart_ids:
        source_charts = dash_result.get("charts", [])
        for c in source_charts:
            if isinstance(c, dict):
                cid = c.get("id")
            elif isinstance(c, (int, str)):
                cid = c
            else:
                continue
            if cid:
                chart_ids.append(int(cid) if isinstance(cid, str) else cid)

    # --- Fetch source charts and datasets ---
    source_ds_map: Dict[int, Dict] = {}
    source_db_map: Dict[int, Dict] = {}
    chart_issues = []

    for cid in chart_ids:
        chart_str = await impl_get_resource(manager, source_server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if not chart_data:
            chart_issues.append({"chart_id": cid, "error": "Chart not found on source"})
            continue

        chart_result = chart_data.get("result", {})
        ds_id = chart_result.get("datasource_id")
        ds_type = chart_result.get("datasource_type", "table")
        chart_name = chart_result.get("slice_name", f"Chart {cid}")

        if ds_id and ds_id not in source_ds_map:
            ds_str = await impl_get_resource(manager, source_server_id, "dataset", ds_id)
            ds_data = _parse_json_result(ds_str)
            if ds_data:
                ds_result = ds_data.get("result", {})
                db_id = ds_result.get("database")
                if isinstance(db_id, dict):
                    db_id = db_id.get("id")

                source_ds_map[ds_id] = {
                    "id": ds_result.get("id"),
                    "name": ds_result.get("table_name", f"Dataset {ds_id}"),
                    "database_id": db_id,
                    "type": "virtual" if ds_result.get("sql") else "physical",
                    "schema": ds_result.get("schema"),
                    "table_name": ds_result.get("table_name")
                }

                if db_id and db_id not in source_db_map:
                    source_db_map[db_id] = {
                        "id": db_id,
                        "name": ds_result.get("database", {}).get("database_name", f"DB {db_id}")
                    }

    # --- Fetch target databases ---
    target_dbs_str = await impl_list_resources(manager, target_server_id, "database")
    target_dbs_data = _parse_json_result(target_dbs_str)
    target_db_list = []
    target_db_by_name: Dict[str, Dict] = {}
    target_db_by_id: Dict[int, Dict] = {}

    if target_dbs_data:
        for db in target_dbs_data.get("result", []):
            target_db_list.append(db)
            target_db_by_name[db.get("database_name", "").lower()] = db
            target_db_by_id[db.get("id")] = db

    # --- Fetch target datasets ---
    target_ds_str = await impl_list_resources(manager, target_server_id, "dataset")
    target_ds_data = _parse_json_result(target_ds_str)
    target_ds_list = []
    target_ds_by_name: Dict[str, Dict] = {}

    if target_ds_data:
        for ds in target_ds_data.get("result", []):
            target_ds_list.append(ds)
            key = f"{ds.get('table_name', '').lower()}|{ds.get('schema', '').lower()}|{ds.get('database', {})}"
            target_ds_by_name[key] = ds

    # --- Check databases ---
    db_check_ok = True
    for db_id, db_info in source_db_map.items():
        db_name = db_info.get("name", "").lower()
        found = False
        matched_target_id = None

        # Try exact name match
        if db_name in target_db_by_name:
            found = True
            matched_target_id = target_db_by_name[db_name]["id"]
        else:
            # Try partial match
            for tdb_name in target_db_by_name:
                if db_name in tdb_name or tdb_name in db_name:
                    found = True
                    matched_target_id = target_db_by_name[tdb_name]["id"]
                    break

        db_result = {
            "source_id": db_id,
            "source_name": db_info.get("name"),
            "exists_on_target": found,
            "target_id": matched_target_id
        }
        checks["databases"].append(db_result)

        if not found:
            db_check_ok = False
            blockers.append(f"Database '{db_info.get('name')}' (ID: {db_id}) not found on target server '{target_server_id}'.")
            recommendations.append(f"Create database '{db_info.get('name')}' on target server with same connection settings, or provide db_mapping during import.")

    # --- Check datasets ---
    ds_check_ok = True
    for ds_id, ds_info in source_ds_map.items():
        ds_name = ds_info.get("name", "").lower()
        ds_schema = (ds_info.get("schema") or "").lower()
        ds_db_id = ds_info.get("database_id")
        ds_type = ds_info.get("type")

        # For physical datasets, check if table exists on target
        found = False
        matched_target_id = None

        if ds_type == "physical":
            # Check if physical dataset with same name exists on target in same DB
            for tds in target_ds_list:
                tds_name = (tds.get("table_name") or "").lower()
                tds_schema = (tds.get("schema") or "").lower()
                tds_db = tds.get("database", {})
                if isinstance(tds_db, dict):
                    tds_db_id = tds_db.get("id")
                else:
                    tds_db_id = tds_db

                if tds_name == ds_name and (tds_schema == ds_schema or not ds_schema) and tds_db_id == ds_db_id:
                    found = True
                    matched_target_id = tds["id"]
                    break
        else:
            # Virtual datasets need to be recreated during import
            found = True  # Virtual datasets will be created
            matched_target_id = None

        ds_result = {
            "source_id": ds_id,
            "source_name": ds_info.get("name"),
            "type": ds_type,
            "exists_on_target": found,
            "target_id": matched_target_id
        }
        checks["datasets"].append(ds_result)

        if not found and ds_type == "physical":
            ds_check_ok = False
            blockers.append(f"Dataset '{ds_info.get('name')}' (ID: {ds_id}) not found on target server.")
            recommendations.append(f"Create physical dataset '{ds_info.get('name')}' on target server, or ensure database '{source_db_map.get(ds_db_id, {}).get('name', 'unknown')}' exists first.")

    # --- Check charts ---
    chart_check_ok = True
    for cid in chart_ids:
        chart_str = await impl_get_resource(manager, source_server_id, "chart", cid)
        chart_data = _parse_json_result(chart_str)
        if not chart_data:
            chart_check_ok = False
            checks["charts"].append({
                "chart_id": cid,
                "error": "Chart not found on source server"
            })
            blockers.append(f"Chart ID {cid} not found on source server.")
            continue

        chart_result = chart_data.get("result", {})
        chart_name = chart_result.get("slice_name", f"Chart {cid}")
        ds_id = chart_result.get("datasource_id")

        # Check if chart's dataset is available
        ds_available = ds_id in source_ds_map
        if not ds_available:
            chart_check_ok = False
            checks["charts"].append({
                "chart_id": cid,
                "chart_name": chart_name,
                "datasource_id": ds_id,
                "dataset_missing": True
            })
            blockers.append(f"Chart '{chart_name}' references dataset ID {ds_id} which could not be resolved.")
            recommendations.append(f"Ensure dataset referenced by chart '{chart_name}' is available on target server.")
        else:
            checks["charts"].append({
                "chart_id": cid,
                "chart_name": chart_name,
                "datasource_id": ds_id,
                "dataset_exists_on_source": True
            })

    # --- Determine overall readiness ---
    can_import = len(blockers) == 0

    # --- Build result ---
    result = {
        "can_import": can_import,
        "dashboard": {
            "id": dashboard_id,
            "name": dashboard_title,
            "source_server": source_server_id,
            "chart_count": len(chart_ids)
        },
        "target_server": target_server_id,
        "checks": checks,
        "summary": {
            "databases_checked": len(source_db_map),
            "datasets_checked": len(source_ds_map),
            "charts_checked": len(chart_ids),
            "databases_missing": sum(1 for c in checks["databases"] if not c.get("exists_on_target")),
            "datasets_missing": sum(1 for c in checks["datasets"] if not c.get("exists_on_target") and c.get("type") == "physical"),
            "chart_issues": len([c for c in checks["charts"] if "error" in c or c.get("dataset_missing")])
        },
        "blockers": blockers,
        "recommendations": recommendations
    }

    if not can_import:
        mc.tool_calls.labels(tool="check_dashboard_import_ready", status="blocked").inc()
    else:
        mc.tool_calls.labels(tool="check_dashboard_import_ready", status="ready").inc()

    mc.tool_duration.labels(tool="check_dashboard_import_ready").observe(time.monotonic() - start_time)

    return json.dumps(result, indent=2, default=str)
