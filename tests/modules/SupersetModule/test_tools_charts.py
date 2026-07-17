import json
import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.SupersetModule.tools import charts
from modules.SupersetModule.tools.charts import (
    list_charts,
    get_chart_info,
    get_chart_api_info,
    create_chart,
    update_chart,
    generate_chart,
    get_chart_preview,
    get_chart_data,
    get_chart_type_schema,
    get_standard_chart_params,
    get_chart_creation_rules,
)
from tests.modules.SupersetModule.conftest import (
    SAMPLE_CHART_LIST,
    SAMPLE_CHART_DETAIL,
    SAMPLE_CHART_DATA,
    make_response,
)


class TestListCharts:
    async def test_returns_chart_list(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_CHART_LIST),
        ):
            result = await list_charts(mock_manager, "test-server")
            data = json.loads(result)
            assert data["count"] == 2
            assert len(data["result"]) == 2
            assert data["result"][0]["slice_name"] == "Chart 1"

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await list_charts(manager, "unknown")
        assert "Error" in result or "error" in result.lower()


class TestGetChartInfo:
    async def test_returns_chart_detail(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_CHART_DETAIL),
        ):
            result = await get_chart_info(mock_manager, "test-server", 1)
            data = json.loads(result)
            assert data["result"]["id"] == 1
            assert data["result"]["slice_name"] == "Chart 1"

    async def test_accepts_string_id(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_CHART_DETAIL),
        ):
            result = await get_chart_info(mock_manager, "test-server", "1")
            data = json.loads(result)
            assert data["result"]["id"] == 1


class TestGetChartApiInfo:
    async def test_returns_api_info(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": {"filters": ["viz_type"]}}),
        ):
            result = await get_chart_api_info(mock_manager, "test-server")
            data = json.loads(result)
            assert "filters" in data.get("result", {})


class TestCreateChart:
    @patch("modules.SupersetModule.tools.charts.auto_fix_chart_params", side_effect=lambda vt, p: p)
    @patch("modules.SupersetModule.tools.charts.validate_chart_params", return_value=[])
    async def test_creates_chart_success(
        self, mock_validate, mock_auto_fix, mock_manager
    ):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data={"id": 42}),
        ):
            result = await create_chart(
                mock_manager, "test-server",
                slice_name="Test Chart",
                viz_type="table",
                datasource_id=1,
                datasource_type="table",
                params="{}",
            )
            data = json.loads(result)
            assert data["id"] == 42

    @patch("modules.SupersetModule.tools.charts.auto_fix_chart_params", side_effect=lambda vt, p: p)
    @patch("modules.SupersetModule.tools.charts.validate_chart_params", return_value=["error"])
    @patch("modules.SupersetModule.tools.charts.format_error_summary", return_value="Warning")
    async def test_creates_chart_with_validation_warning(
        self, mock_format, mock_validate, mock_auto_fix, mock_manager
    ):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data={"id": 1}),
        ):
            result = await create_chart(
                mock_manager, "test-server",
                slice_name="Test",
                viz_type="table",
                datasource_id=1,
                datasource_type="table",
                params="{}",
            )
            data = json.loads(result)
            assert "_validation_warning" in data

    async def test_invalid_json_params(self, mock_manager):
        result = await create_chart(
            mock_manager, "test-server",
            slice_name="Test",
            viz_type="table",
            datasource_id=1,
            datasource_type="table",
            params="not-json",
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert "JSON" in data.get("message", "")

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "400", request=MagicMock(),
                response=make_response(400, {"error": "Bad request"}),
            ),
        ):
            result = await create_chart(
                mock_manager, "test-server",
                slice_name="Test",
                viz_type="table",
                datasource_id=1,
                datasource_type="table",
                params="{}",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await create_chart(
            manager, "unknown",
            slice_name="Test", viz_type="table",
            datasource_id=1, datasource_type="table", params="{}",
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404


class TestUpdateChart:
    async def test_updates_chart(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": "ok"}),
        ):
            result = await update_chart(mock_manager, "test-server", 1, '{"slice_name": "New Name"}')
            data = json.loads(result)
            assert "result" in data


class TestGenerateChart:
    async def test_generates_and_saves_chart(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data={"id": 42}),
        ):
            result = await generate_chart(
                mock_manager, "test-server",
                dataset_id=1,
                config='{"viz_type": "table"}',
                save_chart=True,
            )
            data = json.loads(result)
            assert data["saved"] is True
            assert data["chart_id"] == 42

    async def test_returns_explore_url_when_not_saved(self, mock_manager):
        result = await generate_chart(
            mock_manager, "test-server",
            dataset_id=1,
            config='{"viz_type": "table"}',
            save_chart=False,
        )
        data = json.loads(result)
        assert data["saved"] is False
        assert "url" in data
        assert "explore" in data["url"]

    async def test_invalid_config_json(self, mock_manager):
        result = await generate_chart(
            mock_manager, "test-server",
            dataset_id=1,
            config="not-json",
            save_chart=True,
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert "JSON" in data.get("message", "")

    async def test_http_error_on_save(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "422", request=MagicMock(),
                response=make_response(422, {"error": "Unprocessable"}),
            ),
        ):
            result = await generate_chart(
                mock_manager, "test-server",
                dataset_id=1,
                config='{"viz_type": "table"}',
                save_chart=True,
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await generate_chart(
            manager, "unknown", dataset_id=1, config="{}",
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404


class TestGetChartPreview:
    async def test_returns_preview_url(self, mock_manager):
        result = await get_chart_preview(mock_manager, "test-server", 1)
        data = json.loads(result)
        assert "preview_url" in data
        assert "superset.example.com" in data["preview_url"]
        assert "embed_url" in data
        assert data["chart_id"] == 1

    async def test_accepts_string_id(self, mock_manager):
        result = await get_chart_preview(mock_manager, "test-server", "5")
        data = json.loads(result)
        assert data["chart_id"] == 5

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_chart_preview(manager, "unknown", 1)
        data = json.loads(result)
        assert data.get("error") is True


class TestGetChartData:
    async def test_returns_chart_data(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_CHART_DATA),
        ):
            result = await get_chart_data(mock_manager, "test-server", 1)
            data = json.loads(result)
            assert len(data["result"]) == 2
            assert data["result"][0]["region"] == "North"

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.charts.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(),
                response=make_response(404, {"error": "Not found"}),
            ),
        ):
            result = await get_chart_data(mock_manager, "test-server", 999)
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_chart_data(manager, "unknown", 1)
        data = json.loads(result)
        assert data.get("error") is True


class TestGetChartTypeSchema:
    async def test_returns_schema(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": {"params": ["metric"]}}),
        ):
            result = await get_chart_type_schema(mock_manager, "test-server", "pie")
            data = json.loads(result)
            assert data["chart_type"] == "pie"

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_chart_type_schema(manager, "unknown", "pie")
        data = json.loads(result)
        assert data.get("error") is True


class TestGetStandardChartParams:
    def test_returns_params_dict(self):
        result = get_standard_chart_params("line", 1)
        data = json.loads(result)
        assert data["viz_type"] == "echarts_timeseries_line"

    def test_with_overrides(self):
        result = get_standard_chart_params("line", 1, '{"x_axis": "date"}')
        data = json.loads(result)
        assert data["x_axis"] == "date"

    def test_table_has_query_mode(self):
        result = get_standard_chart_params("table", 1)
        data = json.loads(result)
        assert data["query_mode"] == "raw"


class TestGetChartCreationRules:
    def test_returns_rules_string(self):
        result = get_chart_creation_rules()
        assert isinstance(result, str)
        assert "Superset Chart Creation Rules" in result
        assert "viz_type" in result
