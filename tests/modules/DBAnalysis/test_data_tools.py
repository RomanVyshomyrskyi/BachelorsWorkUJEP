import pytest
import json
from unittest.mock import MagicMock, patch

import sys
import os

from modules.DBAnalysis.tools.data import tool_run_sql, tool_get_table_data


class TestToolRunSql:
    def test_run_sql_success(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = [{"id": 1, "name": "test"}]
            mock_get_strategy.return_value = mock_strategy

            result = tool_run_sql(
                None,
                "SELECT * FROM users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            parsed_result = json.loads(result)
            assert isinstance(parsed_result, list)
            assert len(parsed_result) == 1
            assert parsed_result[0]["id"] == 1

    def test_run_sql_rejects_insert(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.side_effect = ValueError("Security violation")
            mock_get_strategy.return_value = mock_strategy

            result = tool_run_sql(
                None,
                "INSERT INTO users VALUES (1)",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            assert "Error" in result

    def test_run_sql_connection_error(self):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_get_strategy.side_effect = ConnectionError("Failed to connect")

            result = tool_run_sql(
                None,
                "SELECT * FROM users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            assert "Error" in result

    def test_run_sql_returns_json_string(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = [{"col": "value"}]
            mock_get_strategy.return_value = mock_strategy

            result = tool_run_sql(
                None,
                "SELECT 1",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            assert isinstance(result, str)
            parsed = json.loads(result)
            assert isinstance(parsed, list)

    def test_run_sql_with_empty_result(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = []
            mock_get_strategy.return_value = mock_strategy

            result = tool_run_sql(
                None,
                "SELECT * FROM empty_table",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            parsed = json.loads(result)
            assert parsed == []


class TestToolGetTableData:
    def test_get_table_data_success(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = [
                {"id": 1, "name": "Alice"},
                {"id": 2, "name": "Bob"},
            ]
            mock_get_strategy.return_value = mock_strategy

            result = tool_get_table_data(
                None,
                "users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                limit=10,
                port=5432,
            )

            parsed = json.loads(result)
            assert len(parsed) == 2

    def test_get_table_data_default_limit(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = [{"id": 1}]
            mock_get_strategy.return_value = mock_strategy

            tool_get_table_data(
                None,
                "users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                port=5432,
            )

            call_args = mock_strategy.execute_query.call_args[0][0]
            assert "LIMIT 100" in call_args

    def test_get_table_data_custom_limit(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = [{"id": 1}]
            mock_get_strategy.return_value = mock_strategy

            tool_get_table_data(
                None,
                "users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                limit=5,
                port=5432,
            )

            call_args = mock_strategy.execute_query.call_args[0][0]
            assert "LIMIT 5" in call_args

    def test_get_table_data_connection_error(self):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_get_strategy.side_effect = ConnectionError("Connection failed")

            result = tool_get_table_data(
                None,
                "users",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                limit=10,
                port=5432,
            )

            assert "Error" in result

    def test_get_table_data_empty_table(self, valid_connection_details):
        with patch('modules.DBAnalysis.tools.data.get_db_strategy') as mock_get_strategy:
            mock_strategy = MagicMock()
            mock_strategy.__enter__ = MagicMock(return_value=mock_strategy)
            mock_strategy.__exit__ = MagicMock(return_value=False)
            mock_strategy.execute_query.return_value = []
            mock_get_strategy.return_value = mock_strategy

            result = tool_get_table_data(
                None,
                "empty_table",
                db_type="postgres",
                host="localhost",
                user="admin",
                password="admin",
                dbname="test_db",
                limit=10,
                port=5432,
            )

            parsed = json.loads(result)
            assert parsed == []
