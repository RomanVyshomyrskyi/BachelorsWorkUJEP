import json
import pytest
from pydantic import ValidationError

from modules.SupersetModule.schemas.common import (
    SupersetListResponse,
    SupersetDetailResponse,
    PaginationMeta,
    UserInfo,
    InstanceInfo,
)
from modules.SupersetModule.schemas.chart import (
    ChartListItem,
    ChartDetail,
    ChartCreatePayload,
    ChartUpdatePayload,
    ChartPreviewResponse,
    ChartTypeSchema,
)
from modules.SupersetModule.schemas.dashboard import (
    DashboardListItem,
    DashboardDetail,
    DashboardCreatePayload,
    DashboardGenerateResponse,
    ChartLinkResult,
)
from modules.SupersetModule.schemas.dataset import (
    DatasetListItem,
    DatasetDetail,
    VirtualDatasetCreatePayload,
    DatabaseSchemaResponse,
)
from modules.SupersetModule.schemas.database import DatabaseListItem, DatabaseDetail
from modules.SupersetModule.schemas.sqllab import SqlLabUrlResponse
from modules.SupersetModule.schemas.error import ErrorResponse, ErrorDetail


class TestCommonSchemas:
    def test_list_response_empty(self):
        resp = SupersetListResponse()
        assert resp.count == 0
        assert resp.result == []

    def test_list_response_with_items(self):
        resp = SupersetListResponse(count=2, result=[{"id": 1}, {"id": 2}])
        assert resp.count == 2
        assert len(resp.result) == 2

    def test_detail_response(self):
        resp = SupersetDetailResponse(result={"key": "value"})
        assert resp.result["key"] == "value"

    def test_detail_response_error(self):
        resp = SupersetDetailResponse(error="Not found")
        assert resp.error == "Not found"

    def test_user_info_defaults(self):
        u = UserInfo(id=1, username="admin")
        assert u.first_name == ""
        assert u.is_active is True
        assert u.is_anonymous is False

    def test_user_info_full(self):
        u = UserInfo(id=1, username="admin", first_name="A", email="a@b.com")
        assert u.email == "a@b.com"

    def test_instance_info(self):
        info = InstanceInfo(
            user={"id": 1, "username": "admin"},
            features={"dashboards": True},
        )
        assert info.user.username == "admin"
        assert info.features["dashboards"] is True

    def test_pagination_meta_defaults(self):
        p = PaginationMeta()
        assert p.page == 1
        assert p.page_size == 100


class TestChartSchemas:
    def test_chart_list_item(self):
        item = ChartListItem(id=1, slice_name="Chart 1")
        assert item.id == 1
        assert item.slice_name == "Chart 1"

    def test_chart_list_item_partial(self):
        item = ChartListItem(id=1)
        assert item.slice_name is None
        assert item.url is None

    def test_chart_detail_with_optional(self):
        detail = ChartDetail(
            id=1,
            slice_name="Test",
            params={"groupby": ["region"]},
            dashboards=[{"id": 1, "title": "DB"}],
        )
        assert detail.params["groupby"] == ["region"]
        assert len(detail.dashboards) == 1

    def test_chart_create_payload_defaults(self):
        payload = ChartCreatePayload(slice_name="C1", viz_type="pie", datasource_id=1)
        assert payload.datasource_type == "table"
        assert payload.params == "{}"
        assert payload.description is None

    def test_chart_create_payload_full(self):
        payload = ChartCreatePayload(
            slice_name="C1",
            viz_type="pie",
            datasource_id=1,
            params='{"metric": "count"}',
            dashboards=[1, 2],
        )
        assert payload.dashboards == [1, 2]

    def test_chart_update_payload_empty(self):
        payload = ChartUpdatePayload()
        assert payload.slice_name is None
        assert payload.params is None

    def test_chart_preview_response(self):
        preview = ChartPreviewResponse(preview_url="http://example.com/preview", chart_id=1)
        assert preview.preview_url == "http://example.com/preview"
        assert preview.embed_url is None

    def test_chart_preview_with_embed(self):
        preview = ChartPreviewResponse(
            preview_url="http://example.com/preview", chart_id=1, embed_url="http://example.com/embed"
        )
        assert preview.embed_url == "http://example.com/embed"

    def test_chart_type_schema(self):
        schema = ChartTypeSchema(chart_type="pie", schema_data={"metrics": ["count"]})
        assert schema.chart_type == "pie"
        assert schema.schema_data["metrics"] == ["count"]

    def test_chart_type_schema_serialization(self):
        schema = ChartTypeSchema(chart_type="line")
        data = json.loads(schema.model_dump_json())
        assert data["chart_type"] == "line"
        assert data["schema_data"] == {}


class TestDashboardSchemas:
    def test_dashboard_list_item(self):
        item = DashboardListItem(id=1, dashboard_title="DB 1")
        assert item.published is False
        assert item.slug is None

    def test_dashboard_detail_optional(self):
        detail = DashboardDetail(id=1, dashboard_title="DB 1", charts=[{"id": 1}])
        assert len(detail.charts) == 1
        assert detail.owners == []

    def test_dashboard_create_payload_defaults(self):
        payload = DashboardCreatePayload(dashboard_title="DB 1")
        assert payload.owners == []
        assert payload.published is False
        assert payload.position_json == "{}"

    def test_dashboard_generate_response(self):
        resp = DashboardGenerateResponse(id=1, dashboard_title="DB 1", chart_ids=[1, 2])
        assert resp.url is None
        assert len(resp.chart_ids) == 2

    def test_chart_link_result(self):
        result = ChartLinkResult(dashboard_id=1, chart_id=1)
        assert result.success is True
        assert result.message == ""

    def test_chart_link_result_error(self):
        result = ChartLinkResult(dashboard_id=1, chart_id=1, success=False, message="Failed")
        assert result.success is False
        assert result.message == "Failed"


class TestDatasetSchemas:
    def test_dataset_list_item(self):
        item = DatasetListItem(id=1, table_name="sales")
        assert item.database_name is None

    def test_dataset_detail(self):
        detail = DatasetDetail(id=1, table_name="sales", columns=[{"col": "amount"}])
        assert len(detail.columns) == 1
        assert detail.metrics == []

    def test_virtual_dataset_payload(self):
        payload = VirtualDatasetCreatePayload(
            dataset_name="v1", database_id=1, sql="SELECT * FROM t"
        )
        assert payload.schema is None
        assert payload.columns is None

    def test_virtual_dataset_payload_full(self):
        payload = VirtualDatasetCreatePayload(
            dataset_name="v1",
            database_id=1,
            sql="SELECT * FROM t",
            schema="public",
            columns=[{"column_name": "id", "type": "int"}],
        )
        assert payload.schema == "public"
        assert len(payload.columns) == 1

    def test_database_schema_response(self):
        resp = DatabaseSchemaResponse(
            database_id=1, engine="postgresql", tables=[{"name": "sales", "columns": []}]
        )
        assert resp.database_name is None
        assert resp.engine == "postgresql"


class TestDatabaseSchemas:
    def test_database_list_item_defaults(self):
        item = DatabaseListItem(id=1, database_name="test_db")
        assert item.allow_dml is False
        assert item.expose_in_sqllab is True

    def test_database_detail(self):
        detail = DatabaseDetail(id=1, database_name="test_db", backend="postgresql")
        assert detail.owners == []


class TestSqlLabSchemas:
    def test_sql_lab_url_response(self):
        resp = SqlLabUrlResponse(url="http://example.com/sqllab", database_id=1)
        assert resp.sql is None
        assert resp.schema is None

    def test_sql_lab_url_response_full(self):
        resp = SqlLabUrlResponse(
            url="http://example.com/sqllab?sql=SELECT 1", database_id=1, sql="SELECT 1", schema="public"
        )
        assert resp.sql == "SELECT 1"
        assert resp.schema == "public"


class TestErrorSchemas:
    def test_error_response_defaults(self):
        err = ErrorResponse(message="Error occurred")
        assert err.error is True
        assert err.status_code == 500
        assert err.details is None

    def test_error_response_custom(self):
        err = ErrorResponse(
            message="Not found", status_code=404, tool="chart", details="Chart ID 99 missing"
        )
        assert err.status_code == 404
        assert err.details == "Chart ID 99 missing"

    def test_error_detail(self):
        detail = ErrorDetail(message="Error", status_code=400)
        assert detail.tool == ""
