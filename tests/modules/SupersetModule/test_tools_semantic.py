import json
from unittest.mock import MagicMock, patch, AsyncMock
import pytest

from modules.SupersetModule.manager import ConnectionManager
from modules.SupersetModule.tools.semantic import (
    profile_table,
    suggest_metrics,
    suggest_dimensions,
    get_data_dictionary,
)


def _fake_execute_response(client_id: str) -> str:
    return json.dumps({
        "result": {
            "query": {"client_id": client_id, "status": "running"},
        }
    })


def _fake_results_response(data: list) -> str:
    return json.dumps({
        "data": data,
        "status": "success",
        "row_count": len(data),
    })


SAMPLE_COLUMNS = [
    {"column_name": "id", "data_type": "integer", "is_nullable": "NO"},
    {"column_name": "name", "data_type": "varchar", "is_nullable": "YES"},
    {"column_name": "email", "data_type": "varchar", "is_nullable": "YES"},
    {"column_name": "amount", "data_type": "numeric", "is_nullable": "YES"},
    {"column_name": "created_at", "data_type": "timestamp", "is_nullable": "YES"},
    {"column_name": "is_active", "data_type": "boolean", "is_nullable": "YES"},
]

SAMPLE_SCHEMA_RESPONSE = json.dumps({
    "database_id": 1,
    "database_name": "test_db",
    "engine": "postgresql",
    "tables": [
        {"table_name": "orders", "columns": SAMPLE_COLUMNS},
    ],
})


class TestProfileTable:
    @patch("modules.SupersetModule.tools.semantic._profile_table", new_callable=AsyncMock)
    async def test_delegates_to_core(self, mock_core, mock_manager):
        mock_core.return_value = '{"table": "orders", "row_count": 100}'
        result = await profile_table(mock_manager, "test-server", 1, "public", "orders")
        data = json.loads(result)
        assert data["table"] == "orders"

    @patch("modules.SupersetModule.tools.semantic._profile_table", new_callable=AsyncMock)
    async def test_propagates_error(self, mock_core, mock_manager):
        mock_core.return_value = '{"error": true, "message": "Not found"}'
        result = await profile_table(mock_manager, "test-server", 1, "public", "missing")
        data = json.loads(result)
        assert data.get("error") is True


class TestSuggestMetrics:
    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    @patch("modules.SupersetModule.semantic_layer.sqllab_execute_query", new_callable=AsyncMock)
    @patch("modules.SupersetModule.semantic_layer.sqllab_get_query_results", new_callable=AsyncMock)
    async def test_suggests_numeric_columns(self, mock_results, mock_exec, mock_schema, mock_manager):
        mock_schema.return_value = SAMPLE_SCHEMA_RESPONSE
        result = await suggest_metrics(mock_manager, "test-server", 1, "public", "orders")
        data = json.loads(result)
        assert data["table"] == "orders"
        assert len(data["suggested_metrics"]) == 2
        names = [m["column_name"] for m in data["suggested_metrics"]]
        assert "id" in names
        assert "amount" in names

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_table_not_found(self, mock_schema, mock_manager):
        mock_schema.return_value = json.dumps({
            "database_id": 1,
            "tables": [],
        })
        result = await suggest_metrics(mock_manager, "test-server", 1, "public", "ghost")
        data = json.loads(result)
        assert data.get("error") is True

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_no_numeric_means_empty(self, mock_schema, mock_manager):
        mock_schema.return_value = json.dumps({
            "database_id": 1,
            "tables": [
                {
                    "table_name": "labels",
                    "columns": [
                        {"column_name": "name", "data_type": "varchar", "is_nullable": "YES"},
                    ],
                }
            ],
        })
        result = await suggest_metrics(mock_manager, "test-server", 1, "public", "labels")
        data = json.loads(result)
        assert data["suggested_metrics"] == []


class TestSuggestDimensions:
    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_suggests_text_date_bool_columns(self, mock_schema, mock_manager):
        mock_schema.return_value = SAMPLE_SCHEMA_RESPONSE
        result = await suggest_dimensions(mock_manager, "test-server", 1, "public", "orders")
        data = json.loads(result)
        assert data["table"] == "orders"
        names = [d["column_name"] for d in data["suggested_dimensions"]]
        assert "name" in names
        assert "email" in names
        assert "created_at" in names
        assert "is_active" in names
        assert "id" not in names
        assert "amount" not in names

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_assigns_correct_categories(self, mock_schema, mock_manager):
        mock_schema.return_value = SAMPLE_SCHEMA_RESPONSE
        result = await suggest_dimensions(mock_manager, "test-server", 1, "public", "orders")
        data = json.loads(result)
        dims = {d["column_name"]: d["category"] for d in data["suggested_dimensions"]}
        assert dims["name"] == "text"
        assert dims["created_at"] == "date"
        assert dims["is_active"] == "boolean"

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_table_not_found(self, mock_schema, mock_manager):
        mock_schema.return_value = json.dumps({"database_id": 1, "tables": []})
        result = await suggest_dimensions(mock_manager, "test-server", 1, "public", "ghost")
        data = json.loads(result)
        assert data.get("error") is True


class TestGetDataDictionary:
    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    @patch("modules.SupersetModule.semantic_layer.profile_table", new_callable=AsyncMock)
    async def test_builds_dictionary_with_stats(self, mock_profile, mock_schema, mock_manager):
        mock_schema.return_value = SAMPLE_SCHEMA_RESPONSE
        mock_profile.return_value = json.dumps({
            "row_count": 100,
            "numeric_columns": {
                "amount": {
                    "data_type": "numeric", "total": 100, "non_null": 95, "null_count": 5,
                    "null_pct": 5.0, "distinct_count": 80, "min": 10.0, "max": 5000.0,
                    "avg": 250.0, "stddev": 120.0,
                },
            },
            "text_columns": {
                "name": {
                    "data_type": "text", "total": 100, "non_null": 100, "null_count": 0,
                    "null_pct": 0.0, "distinct_count": 90, "min_length": 3, "max_length": 50,
                    "avg_length": 15.5,
                },
            },
            "date_columns": {},
        })
        result = await get_data_dictionary(
            mock_manager, "test-server", 1, "public", "orders",
            include_statistics=True,
        )
        data = json.loads(result)
        assert data["table"] == "orders"
        assert data["row_count"] == 100
        assert len(data["columns"]) == 6
        amount = [c for c in data["columns"] if c["column_name"] == "amount"][0]
        assert amount["category"] == "numeric"
        assert amount["recommended_role"] == "metric"
        assert amount["statistics"]["min"] == 10.0
        name = [c for c in data["columns"] if c["column_name"] == "name"][0]
        assert name["recommended_role"] == "dimension"

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_builds_dictionary_without_stats(self, mock_schema, mock_manager):
        mock_schema.return_value = SAMPLE_SCHEMA_RESPONSE
        result = await get_data_dictionary(
            mock_manager, "test-server", 1, "public", "orders",
            include_statistics=False,
        )
        data = json.loads(result)
        assert data["table"] == "orders"
        assert data["row_count"] is None
        for col in data["columns"]:
            assert "statistics" not in col

    @patch("modules.SupersetModule.semantic_layer._get_schema", new_callable=AsyncMock)
    async def test_table_not_found(self, mock_schema, mock_manager):
        mock_schema.return_value = json.dumps({"database_id": 1, "tables": []})
        result = await get_data_dictionary(mock_manager, "test-server", 1, "public", "ghost")
        data = json.loads(result)
        assert data.get("error") is True


class TestClassifyColumn:
    def _test_cases(self):
        from modules.SupersetModule.semantic_layer import _classify_column
        cases = [
            ("integer", "numeric"), ("bigint", "numeric"), ("numeric", "numeric"),
            ("decimal(10,2)", "numeric"), ("float", "numeric"), ("real", "numeric"),
            ("varchar", "text"), ("character varying", "text"), ("text", "text"),
            ("char(1)", "text"), ("string", "text"),
            ("timestamp", "date"), ("timestamptz", "date"), ("date", "date"),
            ("time", "date"),
            ("boolean", "boolean"), ("bool", "boolean"),
            ("json", "other"), ("jsonb", "other"), ("uuid", "text"),
        ]
        for raw, expected in cases:
            assert _classify_column(raw) == expected, f"Failed: {raw} -> {expected}"


class TestExtractFunctions:
    def test_extract_numeric(self):
        from modules.SupersetModule.semantic_layer import _extract_numeric
        cols = [
            {"column_name": "a", "data_type": "integer"},
            {"column_name": "b", "data_type": "varchar"},
            {"column_name": "c", "data_type": "numeric"},
        ]
        assert _extract_numeric(cols) == ["a", "c"]

    def test_extract_text(self):
        from modules.SupersetModule.semantic_layer import _extract_text
        cols = [
            {"column_name": "a", "data_type": "integer"},
            {"column_name": "b", "data_type": "varchar"},
            {"column_name": "c", "data_type": "text"},
        ]
        assert _extract_text(cols) == ["b", "c"]

    def test_extract_date(self):
        from modules.SupersetModule.semantic_layer import _extract_date
        cols = [
            {"column_name": "a", "data_type": "integer"},
            {"column_name": "b", "data_type": "timestamp"},
            {"column_name": "c", "data_type": "date"},
        ]
        assert _extract_date(cols) == ["b", "c"]
