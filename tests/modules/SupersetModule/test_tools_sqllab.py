import json
import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.SupersetModule.tools.sqllab import (
    sqllab_execute_query,
    sqllab_get_query_results,
    save_sql_query,
    open_sql_lab_with_context,
)
from modules.SupersetModule.tools.explore import generate_explore_link
from tests.modules.SupersetModule.conftest import (
    SAMPLE_SQLLAB_EXECUTE,
    SAMPLE_SQLLAB_RESULTS,
    SAMPLE_SAVED_QUERY,
    make_response,
)


class TestSqlLabExecuteQuery:
    async def test_executes_query(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_SQLLAB_EXECUTE),
        ):
            result = await sqllab_execute_query(
                mock_manager, "test-server",
                database_id=1,
                sql_query="SELECT * FROM sales",
            )
            data = json.loads(result)
            assert data["result"]["query"]["client_id"] == "abc-123"

    async def test_with_all_params(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_SQLLAB_EXECUTE),
        ):
            result = await sqllab_execute_query(
                mock_manager, "test-server",
                database_id=1,
                sql_query="SELECT 1",
                schema="public",
                client_id="my-client",
                tab_name="My Tab",
            )
            data = json.loads(result)
            assert data["result"]["query"]["client_id"] == "abc-123"

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "400", request=MagicMock(),
                response=make_response(400, {"error": "Bad query"}),
            ),
        ):
            result = await sqllab_execute_query(
                mock_manager, "test-server",
                database_id=1,
                sql_query="INVALID SQL",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await sqllab_execute_query(
            manager, "unknown", database_id=1, sql_query="SELECT 1",
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404


class TestSqlLabGetQueryResults:
    async def test_returns_results(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_SQLLAB_RESULTS),
        ):
            result = await sqllab_get_query_results(mock_manager, "test-server", "abc-123")
            data = json.loads(result)
            assert len(data["data"]) == 2
            assert data["data"][0]["region"] == "North"

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "404", request=MagicMock(),
                response=make_response(404, {"error": "Not found"}),
            ),
        ):
            result = await sqllab_get_query_results(mock_manager, "test-server", "unknown-id")
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await sqllab_get_query_results(manager, "unknown", "abc")
        data = json.loads(result)
        assert data.get("error") is True


class TestSaveSqlQuery:
    async def test_saves_query(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data=SAMPLE_SAVED_QUERY),
        ):
            result = await save_sql_query(
                mock_manager, "test-server",
                database_id=1,
                label="My Query",
                sql="SELECT * FROM sales",
            )
            data = json.loads(result)
            assert data["result"]["label"] == "Test Query"

    async def test_with_all_optional_fields(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data=SAMPLE_SAVED_QUERY),
        ):
            result = await save_sql_query(
                mock_manager, "test-server",
                database_id=1,
                label="My Query",
                sql="SELECT 1",
                schema="public",
                description="Test query",
            )
            data = json.loads(result)
            assert data["result"]["label"] == "Test Query"

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.sqllab.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "422", request=MagicMock(),
                response=make_response(422, {"error": "Unprocessable"}),
            ),
        ):
            result = await save_sql_query(
                mock_manager, "test-server",
                database_id=1, label="Q", sql="SELECT 1",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await save_sql_query(
            manager, "unknown", database_id=1, label="Q", sql="SELECT 1",
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestOpenSqlLabWithContext:
    async def test_generates_url_with_basic_params(self, mock_manager):
        result = await open_sql_lab_with_context(
            mock_manager, "test-server", database_id=1,
        )
        data = json.loads(result)
        assert "url" in data
        assert "superset.example.com/sqllab/" in data["url"]
        assert "dbId=1" in data["url"]
        assert data["database_id"] == 1

    async def test_generates_url_with_sql(self, mock_manager):
        result = await open_sql_lab_with_context(
            mock_manager, "test-server",
            database_id=1,
            sql="SELECT * FROM sales",
        )
        data = json.loads(result)
        assert "qtSQL" in data["url"]
        assert data["sql"] == "SELECT * FROM sales"

    async def test_generates_url_with_schema(self, mock_manager):
        result = await open_sql_lab_with_context(
            mock_manager, "test-server",
            database_id=1,
            schema="public",
        )
        data = json.loads(result)
        assert "schema=public" in data["url"]

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await open_sql_lab_with_context(
            manager, "unknown", database_id=1,
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestGenerateExploreLink:
    async def test_generates_url_with_dataset(self, mock_manager):
        result = await generate_explore_link(
            mock_manager, "test-server", dataset_id=42,
        )
        data = json.loads(result)
        assert "url" in data
        assert "explore/" in data["url"]
        assert "datasource_id=42" in data["url"] or "42" in data["url"]
        assert data["dataset_id"] == 42
        assert "permanent" not in data["url"]

    async def test_generates_url_with_config(self, mock_manager):
        result = await generate_explore_link(
            mock_manager, "test-server",
            dataset_id=42,
            config='{"viz_type": "pie"}',
        )
        data = json.loads(result)
        assert "viz_type" in json.dumps(data["config"])

    async def test_invalid_config_json(self, mock_manager):
        result = await generate_explore_link(
            mock_manager, "test-server",
            dataset_id=42,
            config="not-json",
        )
        data = json.loads(result)
        assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await generate_explore_link(
            manager, "unknown", dataset_id=1,
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404
