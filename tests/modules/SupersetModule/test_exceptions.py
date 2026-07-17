import json
import pytest

from modules.SupersetModule.exceptions import (
    SupersetToolError,
    ChartError,
    DashboardError,
    DatasetError,
    DatabaseError,
    SqlLabError,
    ExploreError,
    ServerError,
    TransferError,
)


class TestSupersetToolError:
    def test_base_exception(self):
        exc = SupersetToolError("Something went wrong")
        assert exc.message == "Something went wrong"
        assert exc.status_code == 500
        assert exc.tool == ""
        assert exc.details == ""

    def test_to_json_contains_all_fields(self):
        exc = SupersetToolError("test error", status_code=400, tool="test", details="detail")
        data = json.loads(exc.to_json())
        assert data["error"] is True
        assert data["message"] == "test error"
        assert data["status_code"] == 400
        assert data["tool"] == "test"
        assert data["details"] == "detail"

    def test_to_json_defaults(self):
        exc = SupersetToolError("default error")
        data = json.loads(exc.to_json())
        assert data["status_code"] == 500
        assert data["tool"] == ""

    def test_can_be_raised_and_caught(self):
        try:
            raise SupersetToolError("raised error")
        except SupersetToolError as e:
            assert str(e) == "raised error"


class TestChartError:
    def test_default_tool(self):
        exc = ChartError("chart error", status_code=404)
        assert exc.tool == "chart"
        data = json.loads(exc.to_json())
        assert data["tool"] == "chart"
        assert data["status_code"] == 404

    def test_with_details(self):
        exc = ChartError("bad params", details="invalid metric format")
        data = json.loads(exc.to_json())
        assert data["details"] == "invalid metric format"


class TestDashboardError:
    def test_default_tool(self):
        exc = DashboardError("dashboard error")
        assert exc.tool == "dashboard"
        data = json.loads(exc.to_json())
        assert data["tool"] == "dashboard"


class TestDatasetError:
    def test_default_tool(self):
        exc = DatasetError("dataset error")
        assert exc.tool == "dataset"

    def test_status_code_propagation(self):
        exc = DatasetError("not found", status_code=404)
        assert exc.status_code == 404
        assert exc.tool == "dataset"


class TestDatabaseError:
    def test_default_tool(self):
        exc = DatabaseError("db error")
        data = json.loads(exc.to_json())
        assert data["tool"] == "database"

    def test_custom_status(self):
        exc = DatabaseError("timeout", status_code=503)
        assert exc.status_code == 503


class TestSqlLabError:
    def test_default_tool(self):
        exc = SqlLabError("sql error")
        assert exc.tool == "sqllab"

    def test_json_output(self):
        exc = SqlLabError("syntax error", status_code=400, details="near 'SLECT'")
        data = json.loads(exc.to_json())
        assert data["message"] == "syntax error"
        assert data["details"] == "near 'SLECT'"


class TestExploreError:
    def test_default_tool(self):
        exc = ExploreError("explore error")
        assert exc.tool == "explore"

    def test_is_superset_error(self):
        assert isinstance(ExploreError("x"), SupersetToolError)


class TestServerError:
    def test_default_tool(self):
        exc = ServerError("server error")
        assert exc.tool == "server"


class TestTransferError:
    def test_default_tool(self):
        exc = TransferError("transfer error")
        assert exc.tool == "transfer"

    def test_complex_error(self):
        exc = TransferError(
            "DB not found on target",
            status_code=404,
            details="source_db_id=5, available=[1,2,3]",
        )
        data = json.loads(exc.to_json())
        assert data["message"] == "DB not found on target"
        assert "source_db_id" in data["details"]
