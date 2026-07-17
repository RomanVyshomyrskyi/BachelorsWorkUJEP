import json
import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.SupersetModule.tools import dashboards
from modules.SupersetModule.tools.dashboards import (
    get_dashboard_info,
    get_dashboard_api_info,
    create_dashboard,
    generate_dashboard,
    add_chart_to_existing_dashboard,
    bulk_link_charts,
    update_dashboard,
    generate_simple_dashboard_layout,
    generate_robust_layout,
    _build_simple_layout,
    _add_chart_to_position_json,
    get_dashboard_creation_rules,
)
from tests.modules.SupersetModule.conftest import (
    SAMPLE_DASHBOARD_DETAIL,
    make_response,
)


class TestGetDashboardInfo:
    async def test_returns_dashboard_detail(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DASHBOARD_DETAIL),
        ):
            result = await get_dashboard_info(mock_manager, "test-server", 1)
            data = json.loads(result)
            assert data["result"]["id"] == 1
            assert data["result"]["dashboard_title"] == "Dashboard 1"

    async def test_accepts_string_id(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DASHBOARD_DETAIL),
        ):
            result = await get_dashboard_info(mock_manager, "test-server", "1")
            data = json.loads(result)
            assert data["result"]["id"] == 1


class TestGetDashboardApiInfo:
    async def test_returns_api_info(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": {"filters": ["dashboard_title"]}}),
        ):
            result = await get_dashboard_api_info(mock_manager, "test-server")
            data = json.loads(result)
            assert "filters" in data.get("result", {})


class TestCreateDashboard:
    async def test_creates_dashboard(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data={"id": 1, "dashboard_title": "New DB"}),
        ):
            result = await create_dashboard(
                mock_manager, "test-server",
                dashboard_title="New DB",
                position_json='{"ROOT_ID": {"type": "ROOT"}}',
            )
            data = json.loads(result)
            assert data["id"] == 1

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "422", request=MagicMock(),
                response=make_response(422, {"error": "Unprocessable"}),
            ),
        ):
            result = await create_dashboard(
                mock_manager, "test-server",
                dashboard_title="New DB",
                position_json="{}",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await create_dashboard(
            manager, "unknown", dashboard_title="DB", position_json="{}",
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404


class TestGenerateDashboard:
    async def test_generates_robust_dashboard(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.dashboards.execute_request",
                new_callable=AsyncMock,
                return_value=make_response(status_code=201, json_data={"id": 1}),
            ),
            patch(
                "modules.SupersetModule.tools.dashboards.impl_superset_api",
                new_callable=AsyncMock,
                return_value=json.dumps({"result": "ok"}),
            ),
        ):
            result = await generate_dashboard(
                mock_manager, "test-server",
                dashboard_title="Generated DB",
                chart_ids=[1, 2],
                layout_type="robust",
            )
            data = json.loads(result)
            assert data["id"] == 1

    async def test_generates_simple_dashboard(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.dashboards.execute_request",
                new_callable=AsyncMock,
                return_value=make_response(status_code=201, json_data={"id": 2}),
            ),
            patch(
                "modules.SupersetModule.tools.dashboards.impl_superset_api",
                new_callable=AsyncMock,
                return_value=json.dumps({"result": "ok"}),
            ),
        ):
            result = await generate_dashboard(
                mock_manager, "test-server",
                dashboard_title="Simple DB",
                chart_ids=[1],
                layout_type="simple",
            )
            data = json.loads(result)
            assert data["id"] == 2

    async def test_empty_chart_ids(self, mock_manager):
        result = await generate_dashboard(
            mock_manager, "test-server",
            dashboard_title="Empty DB",
            chart_ids=[],
        )
        data = json.loads(result)
        assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await generate_dashboard(
            manager, "unknown", dashboard_title="DB", chart_ids=[1],
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestAddChartToExistingDashboard:
    async def test_adds_chart(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.dashboards.impl_get_resource",
                new_callable=AsyncMock,
                return_value=json.dumps(SAMPLE_DASHBOARD_DETAIL),
            ),
            patch(
                "modules.SupersetModule.tools.dashboards.execute_request",
                new_callable=AsyncMock,
                return_value=make_response(json_data={"result": "ok"}),
            ),
            patch(
                "modules.SupersetModule.tools.dashboards.impl_superset_api",
                new_callable=AsyncMock,
                return_value=json.dumps({"result": "ok"}),
            ),
        ):
            result = await add_chart_to_existing_dashboard(
                mock_manager, "test-server", dashboard_id=1, chart_id=5
            )
            data = json.loads(result)
            assert data["chart_id"] == 5
            assert data["dashboard_id"] == 1
            assert "message" in data

    async def test_dashboard_not_found(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.impl_get_resource",
            new_callable=AsyncMock,
            return_value='{"error": "not found"}',
        ):
            result = await add_chart_to_existing_dashboard(
                mock_manager, "test-server", dashboard_id=999, chart_id=1
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await add_chart_to_existing_dashboard(
            manager, "unknown", dashboard_id=1, chart_id=1
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestBulkLinkCharts:
    async def test_links_single_chart(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.impl_superset_api",
            new_callable=AsyncMock,
            return_value=json.dumps({"result": "ok"}),
        ):
            result = await bulk_link_charts(mock_manager, "test-server", 1, [5])
            assert "Chart 5" in result

    async def test_links_multiple_charts(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.impl_superset_api",
            new_callable=AsyncMock,
            return_value=json.dumps({"result": "ok"}),
        ):
            result = await bulk_link_charts(mock_manager, "test-server", 1, [1, 2, 3])
            assert "Chart 1" in result
            assert "Chart 2" in result
            assert "Chart 3" in result


class TestUpdateDashboard:
    async def test_updates_dashboard(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": "ok"}),
        ):
            result = await update_dashboard(
                mock_manager, "test-server", 1, '{"dashboard_title": "Updated"}'
            )
            data = json.loads(result)
            assert "result" in data


class TestGenerateSimpleDashboardLayout:
    async def test_generates_layout(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.impl_get_resource",
            new_callable=AsyncMock,
            return_value=json.dumps({
                "result": {"slice_name": "Test Chart", "id": 1}
            }),
        ):
            result = await generate_simple_dashboard_layout(
                mock_manager, "test-server", chart_ids=[1]
            )
            data = json.loads(result)
            assert "ROOT_ID" in data
            assert "GRID_ID" in data
            assert "CHART_1" in data

    async def test_empty_chart_ids(self, mock_manager):
        result = await generate_simple_dashboard_layout(
            mock_manager, "test-server", chart_ids=[]
        )
        data = json.loads(result)
        assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await generate_simple_dashboard_layout(
            manager, "unknown", chart_ids=[1]
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestGenerateRobustLayout:
    async def test_generates_robust_layout(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.dashboards.impl_get_resource",
            new_callable=AsyncMock,
            return_value=json.dumps({"result": {"slice_name": "C1"}}),
        ):
            result = await generate_robust_layout(
                mock_manager, "test-server", chart_ids=[1, 2]
            )
            data = json.loads(result)
            assert "ROOT_ID" in data
            assert "GRID_ID" in data


class TestBuildSimpleLayout:
    def test_single_chart(self):
        layout = _build_simple_layout([{"id": 1, "name": "C1"}])
        assert layout["ROOT_ID"]["children"] == ["GRID_ID"]
        assert layout["GRID_ID"]["children"] == ["ROW-R0"]
        assert layout["ROW-R0"]["children"] == ["CHART_1"]

    def test_two_rows_for_three_charts(self):
        layout = _build_simple_layout([
            {"id": 1, "name": "C1"},
            {"id": 2, "name": "C2"},
            {"id": 3, "name": "C3"},
        ])
        assert len(layout["GRID_ID"]["children"]) == 2
        assert set(layout["ROW-R0"]["children"]) == {"CHART_1", "CHART_2"}
        assert layout["ROW-R1"]["children"] == ["CHART_3"]

    def test_column_layout(self):
        layout = _build_simple_layout(
            [{"id": 1, "name": "C1"}, {"id": 2, "name": "C2"}],
            layout_type="column_of_charts",
        )
        assert layout["CHART_1"]["meta"]["startX"] == 0
        assert layout["CHART_2"]["meta"]["startX"] == 0
        assert layout["CHART_1"]["meta"]["startY"] == 0
        assert layout["CHART_2"]["meta"]["startY"] == 50


class TestAddChartToPositionJson:
    def test_adds_chart_to_existing_layout(self):
        position_json = {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": []},
        }
        result = _add_chart_to_position_json(position_json, 42)
        assert "CHART_42" in result
        assert result["CHART_42"]["meta"]["chartId"] == 42
        assert result["CHART_42"]["type"] == "CHART"

    def test_adds_chart_to_layout_without_grid(self):
        position_json = {"ROOT_ID": {"type": "ROOT", "children": []}}
        result = _add_chart_to_position_json(position_json, 1)
        assert "CHART_1" not in result  # No GRID_ID to attach to


class TestGetDashboardCreationRules:
    def test_returns_rules_string(self):
        result = get_dashboard_creation_rules()
        assert isinstance(result, str)
        assert "Superset Dashboard Creation Rules" in result
