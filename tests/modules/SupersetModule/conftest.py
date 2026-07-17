import json
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import Any, Dict, Optional
import httpx

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.config import SupersetContext, SupersetServerConfig


@pytest.fixture
def mock_context():
    config = MagicMock(spec=SupersetServerConfig)
    config.base_url = "https://superset.example.com"
    config.auth_method = "db"

    ctx = MagicMock(spec=SupersetContext)
    ctx.config = config
    ctx.server_id = "test-server"
    ctx.access_token = "eyJhbGciOiJIUzI1NiJ9.dGVzdC10b2tlbg.test"
    ctx.session_cookie = None
    ctx.csrf_token = None
    ctx.client = AsyncMock()
    ctx.token_path = None
    ctx.token_valid = True

    return ctx


@pytest.fixture
def mock_manager(mock_context):
    manager = MagicMock(spec=ConnectionManager)
    manager.get_context.return_value = mock_context
    return manager


@pytest.fixture(autouse=True)
def mock_auth():
    with (
        patch("modules.SupersetModule.api_client._is_token_expired", return_value=False),
        patch("modules.SupersetModule.api_client._get_csrf_token", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def mock_execute_request():
    with patch("modules.SupersetModule.api_client.execute_request", new_callable=AsyncMock) as mock:
        yield mock


def make_response(status_code: int = 200, json_data: Optional[Any] = None) -> httpx.Response:
    content = json.dumps(json_data).encode() if json_data is not None else b"{}"
    request = httpx.Request("GET", "http://testserver/")
    return httpx.Response(status_code=status_code, content=content, request=request)


def error_response(status_code: int = 400, detail: str = "Bad request") -> httpx.Response:
    return make_response(status_code=status_code, json_data={"error": detail})


def raise_http_error(status_code: int = 400, detail: str = "Bad request"):
    resp = error_response(status_code, detail)
    raise httpx.HTTPStatusError(detail, request=MagicMock(), response=resp)


SAMPLE_CHART_LIST = {
    "count": 2,
    "result": [
        {"id": 1, "slice_name": "Chart 1", "viz_type": "pie", "url": "/chart/1"},
        {"id": 2, "slice_name": "Chart 2", "viz_type": "line", "url": "/chart/2"},
    ],
}

SAMPLE_CHART_DETAIL = {
    "result": {
        "id": 1,
        "slice_name": "Chart 1",
        "viz_type": "pie",
        "params": '{"groupby": ["region"], "metric": "SUM(sales)"}',
        "datasource_id": 42,
        "datasource_type": "table",
        "description": "Test chart",
        "dashboards": [{"id": 1, "dashboard_title": "Dashboard 1"}],
    }
}

SAMPLE_CHART_DATA = {
    "result": [
        {"region": "North", "sales": 100},
        {"region": "South", "sales": 200},
    ]
}

SAMPLE_DASHBOARD_LIST = {
    "count": 2,
    "result": [
        {"id": 1, "dashboard_title": "Dashboard 1", "published": True, "url": "/dashboard/1"},
        {"id": 2, "dashboard_title": "Dashboard 2", "published": False, "url": "/dashboard/2"},
    ],
}

SAMPLE_DASHBOARD_DETAIL = {
    "result": {
        "id": 1,
        "dashboard_title": "Dashboard 1",
        "published": True,
        "position_json": {
            "DASHBOARD_VERSION_KEY": "v2",
            "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"]},
            "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": ["ROW-R0"]},
            "ROW-R0": {
                "type": "ROW", "id": "ROW-R0", "children": ["CHART_1"],
                "meta": {"background": "BACKGROUND_TRANSPARENT"},
            },
            "CHART_1": {
                "type": "CHART", "id": "CHART_1", "children": [],
                "meta": {"chartId": 1, "width": 6, "height": 50},
            },
        },
        "charts": [{"id": 1, "slice_name": "Chart 1"}],
        "owners": [{"id": 1, "username": "admin"}],
    }
}

SAMPLE_DATASET_LIST = {
    "count": 2,
    "result": [
        {"id": 1, "table_name": "sales", "schema": "public", "database_id": 1},
        {"id": 2, "table_name": "users", "schema": "public", "database_id": 1},
    ],
}

SAMPLE_DATASET_DETAIL = {
    "result": {
        "id": 1,
        "table_name": "sales",
        "schema": "public",
        "sql": None,
        "database": {"id": 1, "database_name": "test_db"},
        "columns": [{"column_name": "amount", "type": "numeric"}],
        "metrics": [{"metric_name": "count", "expression": "COUNT(*)"}],
        "owners": [{"id": 1, "username": "admin"}],
    }
}

SAMPLE_DATABASE_LIST = {
    "count": 1,
    "result": [
        {"id": 1, "database_name": "test_db", "backend": "postgresql", "expose_in_sqllab": True},
    ],
}

SAMPLE_DATABASE_DETAIL = {
    "result": {
        "id": 1,
        "database_name": "test_db",
        "backend": "postgresql",
        "expose_in_sqllab": True,
        "allow_dml": False,
        "owners": [{"id": 1, "username": "admin"}],
    }
}

SAMPLE_SQLLAB_EXECUTE = {
    "result": {
        "query": {
            "client_id": "abc-123",
            "query_id": 42,
            "status": "running",
            "sql": "SELECT * FROM sales",
        }
    }
}

SAMPLE_SQLLAB_RESULTS = {
    "data": [
        {"region": "North", "sales": 100},
        {"region": "South", "sales": 200},
    ],
    "columns": [
        {"name": "region", "type": "string"},
        {"name": "sales", "type": "numeric"},
    ],
    "status": "success",
    "row_count": 2,
}

SAMPLE_SAVED_QUERY = {
    "result": {
        "id": 1,
        "label": "Test Query",
        "sql": "SELECT * FROM sales",
        "database_id": 1,
    }
}

SAMPLE_USER_INFO = {
    "result": {
        "id": 1,
        "username": "admin",
        "first_name": "Admin",
        "last_name": "User",
        "email": "admin@example.com",
        "is_active": True,
        "is_anonymous": False,
    }
}

SAMPLE_FEATURES = {
    "result": {
        "feature_flags": True,
        "dashboard_native_filters": True,
    }
}

SAMPLE_SCHEMA = {
    "result": {
        "chart": {
            "filterable_columns": ["slice_name", "viz_type"],
            "sortable_columns": ["id", "slice_name"],
            "default_columns": ["id", "slice_name"],
        }
    }
}

SAMPLE_HEALTH = {"status": "OK"}
