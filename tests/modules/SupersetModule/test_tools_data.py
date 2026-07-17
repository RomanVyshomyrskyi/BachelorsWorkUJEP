import json
import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.SupersetModule.tools.datasets import (
    list_datasets,
    get_dataset_info,
    create_dataset,
    create_virtual_dataset,
)
from modules.SupersetModule.tools.databases import (
    list_databases,
    get_database_info,
)
from tests.modules.SupersetModule.conftest import (
    SAMPLE_DATASET_LIST,
    SAMPLE_DATASET_DETAIL,
    SAMPLE_DATABASE_LIST,
    SAMPLE_DATABASE_DETAIL,
    make_response,
)


class TestListDatasets:
    async def test_returns_list(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DATASET_LIST),
        ):
            result = await list_datasets(mock_manager, "test-server")
            data = json.loads(result)
            assert data["count"] == 2
            assert len(data["result"]) == 2

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await list_datasets(manager, "unknown")
        assert "Error" in result or "error" in result.lower()


class TestGetDatasetInfo:
    async def test_returns_detail(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DATASET_DETAIL),
        ):
            result = await get_dataset_info(mock_manager, "test-server", 1)
            data = json.loads(result)
            assert data["result"]["id"] == 1
            assert data["result"]["table_name"] == "sales"

    async def test_accepts_string_id(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DATASET_DETAIL),
        ):
            result = await get_dataset_info(mock_manager, "test-server", "1")
            data = json.loads(result)
            assert data["result"]["id"] == 1


class TestCreateDataset:
    async def test_creates_dataset(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.datasets.execute_request",
                new_callable=AsyncMock,
                return_value=make_response(status_code=201, json_data={"id": 10}),
            ),
            patch(
                "modules.SupersetModule.tools.datasets.impl_get_resource",
                new_callable=AsyncMock,
                return_value=json.dumps({"result": {"id": 1, "database_name": "test_db"}}),
            ),
        ):
            result = await create_dataset(
                mock_manager, "test-server",
                table_name="new_table",
                database_id=1,
            )
            data = json.loads(result)
            assert data["id"] == 10

    async def test_database_not_found(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.datasets.impl_get_resource",
            new_callable=AsyncMock,
            return_value='{"error": "not found"}',
        ):
            result = await create_dataset(
                mock_manager, "test-server",
                table_name="new_table",
                database_id=999,
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_invalid_metrics_json(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.datasets.impl_get_resource",
            new_callable=AsyncMock,
            return_value=json.dumps({"result": {"id": 1, "database_name": "test_db"}}),
        ):
            result = await create_dataset(
                mock_manager, "test-server",
                table_name="t",
                database_id=1,
                metrics_json="not-json",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_invalid_columns_json(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.datasets.impl_get_resource",
            new_callable=AsyncMock,
            return_value=json.dumps({"result": {"id": 1, "database_name": "test_db"}}),
        ):
            result = await create_dataset(
                mock_manager, "test-server",
                table_name="t",
                database_id=1,
                columns_json="not-json",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_http_error(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.datasets.impl_get_resource",
                new_callable=AsyncMock,
                return_value=json.dumps({"result": {"id": 1, "database_name": "test_db"}}),
            ),
            patch(
                "modules.SupersetModule.tools.datasets.execute_request",
                new_callable=AsyncMock,
                side_effect=httpx.HTTPStatusError(
                    "400", request=MagicMock(),
                    response=make_response(400, {"error": "Bad request"}),
                ),
            ),
        ):
            result = await create_dataset(
                mock_manager, "test-server",
                table_name="t",
                database_id=1,
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await create_dataset(
            manager, "unknown", table_name="t", database_id=1,
        )
        data = json.loads(result)
        assert data.get("error") is True
        assert data.get("status_code") == 404


class TestCreateVirtualDataset:
    async def test_creates_virtual_dataset(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.datasets.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=201, json_data={"id": 20}),
        ):
            result = await create_virtual_dataset(
                mock_manager, "test-server",
                dataset_name="virtual_1",
                database_id=1,
                sql="SELECT * FROM sales",
                schema="public",
            )
            data = json.loads(result)
            assert data["id"] == 20

    async def test_invalid_columns_json(self, mock_manager):
        result = await create_virtual_dataset(
            mock_manager, "test-server",
            dataset_name="v1",
            database_id=1,
            sql="SELECT 1",
            columns_json="not-json",
        )
        data = json.loads(result)
        assert data.get("error") is True

    async def test_http_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.datasets.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(),
                response=make_response(500, {"error": "Server error"}),
            ),
        ):
            result = await create_virtual_dataset(
                mock_manager, "test-server",
                dataset_name="v1",
                database_id=1,
                sql="SELECT 1",
            )
            data = json.loads(result)
            assert data.get("error") is True

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await create_virtual_dataset(
            manager, "unknown", dataset_name="v1", database_id=1, sql="SELECT 1",
        )
        data = json.loads(result)
        assert data.get("error") is True


class TestListDatabases:
    async def test_returns_list(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DATABASE_LIST),
        ):
            result = await list_databases(mock_manager, "test-server")
            data = json.loads(result)
            assert data["count"] == 1
            assert data["result"][0]["database_name"] == "test_db"

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await list_databases(manager, "unknown")
        data = json.loads(result)
        assert data.get("error") is True


class TestGetDatabaseInfo:
    async def test_returns_detail(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_DATABASE_DETAIL),
        ):
            result = await get_database_info(mock_manager, "test-server", 1)
            data = json.loads(result)
            assert data["result"]["id"] == 1
            assert data["result"]["backend"] == "postgresql"

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_database_info(manager, "unknown", 1)
        data = json.loads(result)
        assert data.get("error") is True
