import json
import httpx
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from modules.SupersetModule.tools.system import (
    get_schema,
    get_instance_info,
    health_check,
)
from modules.SupersetModule.tools.server import (
    list_servers,
    reauthenticate,
    server_status,
)
from modules.SupersetModule.tools.general import (
    impl_superset_api,
    superset_api_request,
)
from modules.SupersetModule.tools.resources import (
    list_resource_types,
    list_resources,
    get_resource,
)
from tests.modules.SupersetModule.conftest import (
    SAMPLE_SCHEMA,
    SAMPLE_USER_INFO,
    SAMPLE_FEATURES,
    SAMPLE_HEALTH,
    SAMPLE_CHART_LIST,
    make_response,
)


class TestGetSchema:
    async def test_returns_schema(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_SCHEMA),
        ):
            result = await get_schema(mock_manager, "test-server")
            data = json.loads(result)
            assert "chart" in data["result"]

    async def test_with_model_type(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_SCHEMA),
        ):
            result = await get_schema(mock_manager, "test-server", model_type="chart")
            data = json.loads(result)
            assert "chart" in data["result"]

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_schema(manager, "unknown")
        data = json.loads(result)
        assert data.get("error") is True


class TestGetInstanceInfo:
    async def test_returns_instance_info(self, mock_manager):
        with (
            patch(
                "modules.SupersetModule.tools.general.execute_request",
                new_callable=AsyncMock,
                side_effect=[
                    make_response(json_data=SAMPLE_USER_INFO),
                    make_response(json_data=SAMPLE_FEATURES),
                ],
            ),
        ):
            result = await get_instance_info(mock_manager, "test-server")
            data = json.loads(result)
            assert "user" in data
            assert "features" in data
            assert data["user"]["result"]["username"] == "admin"

    async def test_fallback_on_feature_failure(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            side_effect=[
                make_response(json_data=SAMPLE_USER_INFO),
                httpx.HTTPStatusError(
                    "500", request=MagicMock(),
                    response=make_response(500, {}),
                ),
            ],
        ):
            result = await get_instance_info(mock_manager, "test-server")
            data = json.loads(result)
            assert "user" in data
            assert "features" in data

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await get_instance_info(manager, "unknown")
        data = json.loads(result)
        assert data.get("error") is True


class TestHealthCheck:
    async def test_healthy(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.system.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_HEALTH),
        ):
            result = await health_check(mock_manager, "test-server")
            data = json.loads(result)
            assert data["status"] == "healthy"
            assert data["server_id"] == "test-server"
            assert data["authenticated"] is True

    async def test_degraded(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.system.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=503, json_data={"error": "Overloaded"}),
        ):
            result = await health_check(mock_manager, "test-server")
            data = json.loads(result)
            assert data["status"] == "degraded"
            assert data["status_code"] == 503

    async def test_unreachable(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.system.execute_request",
            new_callable=AsyncMock,
            side_effect=httpx.HTTPStatusError(
                "500", request=MagicMock(),
                response=make_response(500, {}),
            ),
        ):
            result = await health_check(mock_manager, "test-server")
            data = json.loads(result)
            assert data["status"] == "unhealthy"

    async def test_connection_error(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.system.execute_request",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await health_check(mock_manager, "test-server")
            data = json.loads(result)
            assert data["status"] == "unreachable"

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await health_check(manager, "unknown")
        data = json.loads(result)
        assert data.get("error") is True


class TestListServers:
    async def test_returns_server_list(self):
        manager = MagicMock()
        ctx = MagicMock()
        ctx.config.base_url = "https://superset.example.com"
        ctx.config.auth_method = "db"
        manager._contexts = {"server1": ctx}
        result = await list_servers(manager)
        assert "server1" in result

    async def test_empty_list(self):
        manager = MagicMock()
        manager._contexts = {}
        cfg = type("cfg", (), {})()
        cfg.config_dir = "/tmp"
        manager._config_dir = "/tmp"
        result = await list_servers(manager)
        assert "No servers" in result or "Debug" in result


class TestReauthenticate:
    async def test_reauthenticate_success(self, mock_manager):
        mock_context = mock_manager.get_context.return_value
        mock_context.access_token = "new-token"

        with patch(
            "modules.SupersetModule.tools.server.authenticate",
            new_callable=AsyncMock,
            side_effect=lambda ctx: setattr(ctx, "access_token", "new-token"),
        ):
            result = await reauthenticate(mock_manager, "test-server")
            assert "Successfully" in result

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await reauthenticate(manager, "unknown")
        assert "Error" in result or "not found" in result.lower()


class TestServerStatus:
    async def test_online(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.server.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(
                json_data={"result": {"username": "admin"}},
            ),
        ):
            result = await server_status(mock_manager, "test-server")
            assert "ONLINE" in result
            assert "admin" in result

    async def test_reachable_but_not_200(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.server.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(status_code=302),
        ):
            result = await server_status(mock_manager, "test-server")
            assert "REACHABLE" in result

    async def test_offline(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.server.execute_request",
            new_callable=AsyncMock,
            side_effect=Exception("Connection refused"),
        ):
            result = await server_status(mock_manager, "test-server")
            assert "OFFLINE" in result

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await server_status(manager, "unknown")
        assert "Error" in result or "not found" in result.lower()


class TestImplSupersetApi:
    async def test_get_request(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": "ok"}),
        ):
            result = await impl_superset_api(mock_manager, "test-server", "GET", "/api/v1/chart/")
            data = json.loads(result)
            assert data["result"] == "ok"

    async def test_post_request(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"id": 1}),
        ):
            result = await impl_superset_api(
                mock_manager, "test-server", "POST", "/api/v1/chart/",
                json_body='{"name": "test"}',
            )
            data = json.loads(result)
            assert data["id"] == 1

    async def test_delete_forbidden(self, mock_manager):
        result = await impl_superset_api(mock_manager, "test-server", "DELETE", "/api/v1/chart/1")
        assert "forbidden" in result.lower() or "DELETE" in result

    async def test_server_not_found(self):
        manager = MagicMock()
        manager.get_context.return_value = None
        result = await impl_superset_api(manager, "unknown", "GET", "/api/v1/chart/")
        assert "Error" in result or "not found" in result


class TestSupersetApiRequest:
    async def test_delegates_to_impl(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": "ok"}),
        ):
            result = await superset_api_request(
                mock_manager, "test-server", "GET", "/api/v1/chart/"
            )
            data = json.loads(result)
            assert data["result"] == "ok"


class TestListResourceTypes:
    async def test_returns_types(self):
        result = await list_resource_types()
        assert "Available Resource Types" in result
        assert "chart" in result
        assert "dashboard" in result
        assert "database" in result
        assert "dataset" in result

    async def test_actual_list_resources(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data=SAMPLE_CHART_LIST),
        ):
            result = await list_resources(mock_manager, "test-server", "chart")
            data = json.loads(result)
            assert data["count"] == 2


class TestGetResource:
    async def test_gets_resource(self, mock_manager):
        with patch(
            "modules.SupersetModule.tools.general.execute_request",
            new_callable=AsyncMock,
            return_value=make_response(json_data={"result": {"id": 1, "name": "test"}}),
        ):
            result = await get_resource(mock_manager, "test-server", "dashboard", 1)
            data = json.loads(result)
            assert data["result"]["id"] == 1
