import json
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from modules.SupersetModule.tools.transfer import (
    _extract_sql_from_params,
    _extract_fields_from_params,
    _compute_diff_str,
    transfer_dashboard,
)


class TestExtractSqlFromParams:
    def test_from_dict_params(self):
        params = {"sql": "SELECT * FROM sales"}
        assert _extract_sql_from_params(params) == "SELECT * FROM sales"

    def test_from_json_string(self):
        assert _extract_sql_from_params('{"sql": "SELECT 1"}') == "SELECT 1"

    def test_sql_in_query_key(self):
        assert _extract_sql_from_params({"query": "SELECT * FROM users"}) == "SELECT * FROM users"

    def test_sql_in_where(self):
        assert _extract_sql_from_params({"where": "amount > 100"}) == "amount > 100"

    def test_no_sql(self):
        assert _extract_sql_from_params({"groupby": ["region"]}) is None

    def test_empty_string(self):
        assert _extract_sql_from_params("") is None

    def test_invalid_json(self):
        assert _extract_sql_from_params("not-json") is None


class TestExtractFieldsFromParams:
    def test_extracts_metric_groupby(self):
        p = {"metric": "SUM(sales)", "groupby": ["region"], "row_limit": 100}
        f = _extract_fields_from_params(p)
        assert f["metrics"] == "SUM(sales)"
        assert f["groupby"] == ["region"]
        assert f["row_limit"] == 100

    def test_extracts_metrics_array(self):
        p = {"metrics": ["count", "SUM(sales)"]}
        f = _extract_fields_from_params(p)
        assert f["metrics"] == ["count", "SUM(sales)"]

    def test_extracts_filters(self):
        p = {"ad-hoc_filters": [{"col": "region", "op": "=="}]}
        f = _extract_fields_from_params(p)
        assert f["filters"] == [{"col": "region", "op": "=="}]

    def test_extracts_granularity(self):
        p = {"time_grain_sqla": "P1D"}
        f = _extract_fields_from_params(p)
        assert f["granularity"] == "P1D"

    def test_empty_params(self):
        f = _extract_fields_from_params({})
        assert f.get("metrics") is None or f.get("metrics") == []
        assert f.get("groupby") is None or f.get("groupby") == []
        assert f.get("row_limit") is None


class TestComputeDiffStr:
    def test_identical(self):
        d = _compute_diff_str({"a": 1, "b": 2}, {"a": 1, "b": 2})
        assert "(identical)" in d

    def test_different_values(self):
        d = _compute_diff_str({"metric": "SUM(x)"}, {"metric": "AVG(x)"})
        assert "metric" in d
        assert "SUM(x)" in d
        assert "AVG(x)" in d

    def test_missing_key(self):
        d = _compute_diff_str({"a": 1}, {"b": 2})
        assert "a" in d
        assert "b" in d


class TestTransferDashboardReport:
    @patch("modules.SupersetModule.tools.transfer.impl_get_resource", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer.impl_list_resources", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._resolve_dataset", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._recreate_chart", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.create_dashboard", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.bulk_link_charts", new_callable=AsyncMock)
    @patch("modules.SupersetModule.api_client._is_token_expired", return_value=False)
    @patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock)
    async def test_report_contains_source_destination(
        self, mock_csrf, mock_expired,
        mock_bulk, mock_create_dash, mock_recreate, mock_resolve,
        mock_list_res, mock_get_res,
    ):
        mock_get_res.side_effect = _mock_get_resource
        mock_list_res.return_value = json.dumps({"result": []})  # no matching charts at destination
        mock_resolve.return_value = (100, "table", None)
        mock_recreate.return_value = (200, None)
        mock_create_dash.return_value = json.dumps({"id": 300})
        mock_bulk.return_value = "ok"

        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://source.example.com"
        ctx.server_id = "source"
        ctx.access_token = "tok"
        ctx.session_cookie = None
        ctx.csrf_token = None
        ctx.client = AsyncMock()
        ctx.token_path = None
        ctx.token_valid = True
        manager.get_context.return_value = ctx

        result = await transfer_dashboard(manager, "source", "target", 5)
        data = json.loads(result)
        assert "_report" in data
        report = data["_report"]
        assert report["source"]["server_id"] == "source"
        assert report["destination"]["server_id"] == "target"
        assert report["dashboard"]["id"] == 5
        assert report["dashboard"]["chart_count"] == 2
        assert len(report["dashboard"]["charts"]) == 2

    @patch("modules.SupersetModule.tools.transfer.impl_get_resource", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer.impl_list_resources", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._resolve_dataset", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._recreate_chart", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.create_dashboard", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.bulk_link_charts", new_callable=AsyncMock)
    @patch("modules.SupersetModule.api_client._is_token_expired", return_value=False)
    @patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock)
    async def test_report_has_execution_timeline(
        self, mock_csrf, mock_expired,
        mock_bulk, mock_create_dash, mock_recreate, mock_resolve,
        mock_list_res, mock_get_res,
    ):
        mock_get_res.side_effect = _mock_get_resource
        mock_list_res.return_value = json.dumps({"result": []})
        mock_resolve.return_value = (100, "table", None)
        mock_recreate.return_value = (200, None)
        mock_create_dash.return_value = json.dumps({"id": 300})
        mock_bulk.return_value = "ok"

        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://source.example.com"
        ctx.server_id = "source"
        ctx.access_token = "tok"
        ctx.session_cookie = None
        ctx.csrf_token = None
        ctx.client = AsyncMock()
        ctx.token_path = None
        ctx.token_valid = True
        manager.get_context.return_value = ctx

        result = await transfer_dashboard(manager, "source", "target", 5)
        data = json.loads(result)
        report = data["_report"]
        assert len(report["execution"]["datasets"]) == 1
        assert len(report["execution"]["charts"]) == 2
        assert report["execution"]["dashboard"]["status"] == "success"
        assert report["execution"]["dashboard"]["target_id"] == 300

    @patch("modules.SupersetModule.tools.transfer.impl_get_resource", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer.impl_list_resources", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._resolve_dataset", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._recreate_chart", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.create_dashboard", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.bulk_link_charts", new_callable=AsyncMock)
    @patch("modules.SupersetModule.api_client._is_token_expired", return_value=False)
    @patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock)
    async def test_report_contains_chart_details(
        self, mock_csrf, mock_expired,
        mock_bulk, mock_create_dash, mock_recreate, mock_resolve,
        mock_list_res, mock_get_res,
    ):
        mock_get_res.side_effect = _mock_get_resource
        mock_list_res.return_value = json.dumps({"result": []})
        mock_resolve.return_value = (100, "table", None)
        mock_recreate.return_value = (200, None)
        mock_create_dash.return_value = json.dumps({"id": 300})
        mock_bulk.return_value = "ok"

        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://source.example.com"
        ctx.server_id = "source"
        ctx.access_token = "tok"
        ctx.session_cookie = None
        ctx.csrf_token = None
        ctx.client = AsyncMock()
        ctx.token_path = None
        ctx.token_valid = True
        manager.get_context.return_value = ctx

        result = await transfer_dashboard(manager, "source", "target", 5)
        data = json.loads(result)
        report = data["_report"]
        chart = report["dashboard"]["charts"][0]
        assert "slice_name" in chart
        assert "viz_type" in chart
        assert "params" in chart
        assert "sql" in chart
        assert "datasource_id" in chart

    @patch("modules.SupersetModule.tools.transfer.impl_get_resource", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer.impl_list_resources", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._resolve_dataset", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._recreate_chart", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.create_dashboard", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.bulk_link_charts", new_callable=AsyncMock)
    @patch("modules.SupersetModule.api_client._is_token_expired", return_value=False)
    @patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock)
    async def test_report_has_success_rate(
        self, mock_csrf, mock_expired,
        mock_bulk, mock_create_dash, mock_recreate, mock_resolve,
        mock_list_res, mock_get_res,
    ):
        mock_get_res.side_effect = _mock_get_resource
        mock_list_res.return_value = json.dumps({"result": []})
        mock_resolve.return_value = (100, "table", None)
        mock_recreate.return_value = (200, None)
        mock_create_dash.return_value = json.dumps({"id": 300})
        mock_bulk.return_value = "ok"

        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://source.example.com"
        ctx.server_id = "source"
        ctx.access_token = "tok"
        ctx.session_cookie = None
        ctx.csrf_token = None
        ctx.client = AsyncMock()
        ctx.token_path = None
        ctx.token_valid = True
        manager.get_context.return_value = ctx

        result = await transfer_dashboard(manager, "source", "target", 5)
        data = json.loads(result)
        report = data["_report"]
        assert "success_rate" in report
        assert "%" in report["success_rate"]
        assert "total_duration_ms" in report

    @patch("modules.SupersetModule.tools.transfer.impl_get_resource", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer.impl_list_resources", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._resolve_dataset", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.transfer._recreate_chart", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.create_dashboard", new_callable=AsyncMock)
    @patch("modules.SupersetModule.tools.dashboards.bulk_link_charts", new_callable=AsyncMock)
    @patch("modules.SupersetModule.api_client._is_token_expired", return_value=False)
    @patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock)
    async def test_report_finds_destination_diff(
        self, mock_csrf, mock_expired,
        mock_bulk, mock_create_dash, mock_recreate, mock_resolve,
        mock_list_res, mock_get_res,
    ):
        mock_get_res.side_effect = _mock_get_resource
        mock_list_res.return_value = json.dumps({
            "result": [
                {"id": 99, "slice_name": "Revenue Trend", "viz_type": "line",
                 "params": '{"metric": "AVG(sales)"}'},
            ]
        })
        mock_resolve.return_value = (100, "table", None)
        mock_recreate.return_value = (200, None)
        mock_create_dash.return_value = json.dumps({"id": 300})
        mock_bulk.return_value = "ok"

        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://source.example.com"
        ctx.server_id = "source"
        ctx.access_token = "tok"
        ctx.session_cookie = None
        ctx.csrf_token = None
        ctx.client = AsyncMock()
        ctx.token_path = None
        ctx.token_valid = True
        manager.get_context.return_value = ctx

        result = await transfer_dashboard(manager, "source", "target", 5)
        data = json.loads(result)
        report = data["_report"]
        assert len(report["diffs"]) >= 1
        diff = report["diffs"][0]
        assert diff["exists_in_destination"] is True
        assert "diff" in diff


def _mock_get_resource(manager, server_id, resource_type, item_id):
    if resource_type == "dashboard":
        return json.dumps({
            "result": {
                "id": item_id,
                "dashboard_title": "Sales Dashboard",
                "charts": [
                    {"id": 10, "slice_name": "Revenue Trend"},
                    {"id": 11, "slice_name": "Region Breakdown"},
                ],
            }
        })
    if resource_type == "chart":
        charts = {
            10: {
                "id": 10, "slice_name": "Revenue Trend", "viz_type": "line",
                "datasource_id": 1, "datasource_type": "table",
                "params": '{"metric": "SUM(sales)", "groupby": ["month"]}',
            },
            11: {
                "id": 11, "slice_name": "Region Breakdown", "viz_type": "pie",
                "datasource_id": 1, "datasource_type": "table",
                "params": '{"metric": "count", "groupby": ["region"]}',
            },
        }
        return json.dumps({"result": charts.get(item_id, {})})
    if resource_type == "database":
        return json.dumps({
            "result": {"id": item_id, "database_name": "test_db", "backend": "postgresql"}
        })
    if resource_type == "dataset":
        return json.dumps({
            "result": {
                "id": item_id, "table_name": "orders", "schema": "public",
                "sql": None, "database": {"id": 1, "database_name": "test_db"},
            }
        })
    return json.dumps({"result": {}})
